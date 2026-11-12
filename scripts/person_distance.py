"""Measure each person's box centre or confident pose nodes from an assumed origin."""
import json
import math

import message_filters
import numpy as np
import rclpy
from cv_bridge import CvBridge, CvBridgeError
from geometry_msgs.msg import Pose, PoseArray
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray
from yolo_msgs.msg import DetectionArray
from keypoint_distance import SELECTION_POLICIES, measure_keypoints


def measure_center(depth_m, u, v, k):
    """Use the centre pixel's optical depth, with x forward, y left, z up."""
    height, width = depth_m.shape
    if not (math.isfinite(u) and math.isfinite(v) and 0 <= u < width and 0 <= v < height):
        raise ValueError('box_center_outside_image')
    fx, fy, cx, cy = k[0], k[4], k[2], k[5]
    if not all(math.isfinite(value) for value in (fx, fy, cx, cy)) or fx <= 0 or fy <= 0:
        raise ValueError('invalid_camera_intrinsics')
    pixel_u = min(width - 1, int(u + .5))
    pixel_v = min(height - 1, int(v + .5))
    depth = float(depth_m[pixel_v, pixel_u])
    if not math.isfinite(depth) or depth <= 0:
        raise ValueError('invalid_center_depth')
    # The camera is assumed to be at the robot origin, level and facing forward.
    x = depth
    y = -(u - cx) * depth / fx
    z = -(v - cy) * depth / fy
    yaw = math.atan2(y, x)
    return {'sample_pixel': {'u': pixel_u, 'v': pixel_v}, 'depth_m': depth,
            'position_m': {'x': x, 'y': y, 'z': z},
            'distance_m': math.sqrt(x*x + y*y + z*z),
            'ground_distance_m': math.hypot(x, y),
            'turn_yaw_rad': yaw, 'turn_yaw_deg': math.degrees(yaw)}


class PersonDistance(Node):
    def __init__(self):
        super().__init__('person_distance', parameter_overrides=[Parameter('use_sim_time', value=True)])
        self.bridge = CvBridge()
        self.method = self.declare_parameter('method', 'box_center').value
        self.threshold = self.declare_parameter('keypoint_threshold', .7).value
        self.min_points = self.declare_parameter('minimum_keypoints', 3).value
        self.outlier_tolerance = self.declare_parameter('outlier_tolerance_m', .5).value
        self.outlier_mad_scale = self.declare_parameter('outlier_mad_scale', 3.).value
        self.selection_policy = self.declare_parameter('selection_policy', 'all_valid').value
        if self.method not in ('box_center', 'keypoint_mean'):
            raise ValueError('method must be box_center or keypoint_mean')
        if self.selection_policy not in SELECTION_POLICIES:
            raise ValueError('invalid_selection_policy')
        if not math.isfinite(self.threshold) or not 0 <= self.threshold <= 1 or self.min_points < 1:
            raise ValueError('invalid_keypoint_parameters')
        if not all(math.isfinite(v) and v > 0 for v in (self.outlier_tolerance, self.outlier_mad_scale)):
            raise ValueError('invalid_depth_outlier_parameters')
        self.distances = self.create_publisher(String, '/perception/people/distances', 10)
        self.poses = self.create_publisher(PoseArray, '/perception/people/center_poses', 10)
        self.detections = message_filters.Subscriber(
            self, DetectionArray if self.method == 'keypoint_mean' else Detection2DArray,
            '/perception/people/poses2d' if self.method == 'keypoint_mean' else '/perception/people/detections2d',
            qos_profile=10)
        self.depth = message_filters.Subscriber(
            self, Image, '/oakd/rgb/preview/depth', qos_profile=qos_profile_sensor_data)
        self.info = message_filters.Subscriber(
            self, CameraInfo, '/oakd/rgb/preview/camera_info', qos_profile=qos_profile_sensor_data)
        # Require the same source frame; never combine a box with a newer depth image.
        self.sync = message_filters.TimeSynchronizer([self.detections, self.depth, self.info], 20)
        self.sync.registerCallback(self.receive)

    def receive(self, detections, depth, info):
        output = {'stamp': {'sec': detections.header.stamp.sec, 'nanosec': detections.header.stamp.nanosec},
                  'frame_id': 'assumed_robot',
                  'robot_position_m': {'x': 0.0, 'y': 0.0, 'z': 0.0},
                  'robot_yaw_rad': 0.0, 'people': []}
        output['method'] = self.method
        if self.method == 'keypoint_mean':
            output['selection_policy'] = self.selection_policy
        poses = PoseArray()
        poses.header.stamp = detections.header.stamp
        poses.header.frame_id = 'assumed_robot'
        image = None
        error = None
        try:
            if depth.encoding not in ('32FC1', '16UC1'):
                raise ValueError('unsupported_depth_encoding')
            if depth.width != info.width or depth.height != info.height:
                raise ValueError('depth_camera_info_size_mismatch')
            if any(not math.isfinite(value) or abs(value) > 1e-9 for value in info.d):
                raise ValueError('rectified_aligned_images_required')
            image = self.bridge.imgmsg_to_cv2(depth, 'passthrough').astype(np.float32)
            if depth.encoding == '16UC1':
                image *= .001
        except (ValueError, CvBridgeError) as exc:
            error = str(exc)
        for index, detection in enumerate(detections.detections):
            pose_mode = self.method == 'keypoint_mean'
            if not pose_mode and (not detection.results or detection.results[0].hypothesis.class_id != 'person'):
                continue
            u = float(detection.bbox.center.position.x)
            v = float(detection.bbox.center.position.y)
            score = float(detection.score if pose_mode else detection.results[0].hypothesis.score)
            person = {'detection_index': index, 'valid': False,
                      'score': score if math.isfinite(score) else None,
                      'center_px': {'u': u if math.isfinite(u) else None,
                                    'v': v if math.isfinite(v) else None}}
            try:
                if error:
                    raise ValueError(error)
                if pose_mode:
                    nodes = [(p.id, p.point.x, p.point.y, p.score) for p in detection.keypoints.data]
                    person.update(measure_keypoints(image, nodes, info.k, self.threshold, self.min_points,
                                                    self.outlier_tolerance, self.outlier_mad_scale,
                                                    self.selection_policy))
                else:
                    person.update(measure_center(image, u, v, info.k))
                    person['valid'] = True
                if not person['valid']:
                    output['people'].append(person)
                    continue
                pose = Pose()
                point = person['position_m']
                pose.position.x, pose.position.y, pose.position.z = point['x'], point['y'], point['z']
                # Orientation is the heading towards the point, not the person's facing direction.
                pose.orientation.z = math.sin(person['turn_yaw_rad'] / 2)
                pose.orientation.w = math.cos(person['turn_yaw_rad'] / 2)
                poses.poses.append(pose)
            except ValueError as exc:
                person['reason'] = str(exc)
            output['people'].append(person)
        message = String()
        message.data = json.dumps(output, allow_nan=False)
        self.distances.publish(message)
        self.poses.publish(poses)


def main():
    rclpy.init()
    node = PersonDistance()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
