"""Fuse same-stamp detections, depth and calibration into camera-relative estimates."""
import json
import math

from cv_bridge import CvBridge
from message_filters import Subscriber, TimeSynchronizer
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray

from depth_estimation import estimate_depth


DEPTH_TOPIC = '/oakd/rgb/preview/depth'
INFO_TOPIC = '/oakd/rgb/preview/camera_info'
DETECTION_TOPIC = '/perception/people/detections2d'
OUTPUT_TOPIC = '/perception/people/depth_estimates'
RGBD_QOS = QoSProfile(depth=20, reliability=ReliabilityPolicy.BEST_EFFORT)


def stamp_ns(header):
    return header.stamp.sec * 1_000_000_000 + header.stamp.nanosec


def box_xyxy(bbox):
    x, y = bbox.center.position.x, bbox.center.position.y
    w, h = bbox.size_x / 2, bbox.size_y / 2
    return [x - w, y - h, x + w, y + h]


def camera_intrinsics(info):
    values = [info.k[i] for i in (0, 4, 2, 5)]
    if not all(math.isfinite(value) for value in values) or min(values[:2]) <= 0:
        raise ValueError('Missing pinhole calibration')
    if any(not math.isfinite(value) or abs(value) > 1e-8 for value in info.d):
        raise ValueError('This node requires aligned images with zero distortion')
    return values


class PersonDepth(Node):
    def __init__(self):
        super().__init__('person_depth_estimator')
        self.bridge = CvBridge()
        self.publisher = self.create_publisher(String, OUTPUT_TOPIC, 10)
        self.inputs = [Subscriber(self, Detection2DArray, DETECTION_TOPIC, qos_profile=10),
                       Subscriber(self, Image, DEPTH_TOPIC, qos_profile=RGBD_QOS),
                       Subscriber(self, CameraInfo, INFO_TOPIC, qos_profile=RGBD_QOS)]
        self.sync = TimeSynchronizer(self.inputs, 20)
        self.sync.registerCallback(self.receive)

    def receive(self, detections, depth, info):
        frame = {'schema_version': 1, 'stamp_ns': stamp_ns(detections.header),
                 'image_frame_id': info.header.frame_id, 'coordinate_axes': 'optical',
                 'status': 'paired', 'estimates': []}
        if (not info.header.frame_id or detections.header.frame_id != info.header.frame_id
                or depth.header.frame_id != info.header.frame_id
                or (depth.width, depth.height) != (info.width, info.height)):
            frame['status'] = 'incompatible_image_geometry'
        elif depth.encoding != '32FC1':
            frame['status'] = 'unsupported_depth_encoding'
        else:
            try:
                intrinsics = camera_intrinsics(info)
            except ValueError:
                frame['status'] = 'invalid_intrinsics'
            else:
                image = self.bridge.imgmsg_to_cv2(depth, desired_encoding='passthrough')
                for index, detection in enumerate(detections.detections):
                    box = box_xyxy(detection.bbox)
                    estimate = estimate_depth(image, box, intrinsics)
                    frame['estimates'].append(dict(estimate, detection_index=index, bbox=box))
        self.publisher.publish(String(data=json.dumps(frame, allow_nan=False)))


if __name__ == '__main__':
    rclpy.init()
    node = PersonDepth()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
