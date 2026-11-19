"""Measure each person's box centre relative to an assumed robot at (0, 0, 0)."""
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
        self.distances = self.create_publisher(String, '/perception/people/distances', 10)
        self.poses = self.create_publisher(PoseArray, '/perception/people/center_poses', 10)
        self.detections = message_filters.Subscriber(
            self, Detection2DArray, '/perception/people/detections2d', qos_profile=10)
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
            if not detection.results or detection.results[0].hypothesis.class_id != 'person':
                continue
            u = float(detection.bbox.center.position.x)
            v = float(detection.bbox.center.position.y)
            score = float(detection.results[0].hypothesis.score)
            person = {'detection_index': index, 'valid': False,
                      'score': score if math.isfinite(score) else None,
                      'center_px': {'u': u if math.isfinite(u) else None,
                                    'v': v if math.isfinite(v) else None}}
            try:
                if error:
                    raise ValueError(error)
                person.update(measure_center(image, u, v, info.k))
                person['valid'] = True
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
