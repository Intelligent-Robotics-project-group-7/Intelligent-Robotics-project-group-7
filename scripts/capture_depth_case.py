"""Record independent simulator poses and exact-stamp RGB-D evaluation inputs."""
import argparse
from bisect import bisect_left
import json
from pathlib import Path
from threading import Lock
import time

from cv_bridge import CvBridge
from gz.msgs10.pose_v_pb2 import Pose_V
from gz.transport13 import Node as GzNode
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray

from person_depth_node import (DEPTH_TOPIC, DETECTION_TOPIC, INFO_TOPIC, OUTPUT_TOPIC, RGBD_QOS,
                               box_xyxy, camera_intrinsics, stamp_ns)
from prepare_person_world import load_settings


ROOT = Path(__file__).resolve().parents[1]
RGB_TOPIC = '/oakd/rgb/preview/image_raw'
LABEL_TOPIC = '/evaluation/semantic/labels_map'


class Capture(Node):
    def __init__(self, start_ns, stop_ns, case):
        super().__init__('phase3_depth_evaluator')
        self.start_ns, self.stop_ns = start_ns, stop_ns
        self.bridge = CvBridge()
        self.data = {name: {} for name in ('rgb', 'depth', 'labels', 'info', 'boxes', 'output')}
        self.latest_clock = 0
        self.pose_lock = Lock()
        self.poses = {}
        self.last_pose_names = []
        self.pose_names = {'turtlebot4', 'oakd_rgb_camera_frame'}
        self.pose_names.update(f'person_{index}' for index in range(1, len(case['actors']) + 1))
        if case['category'] == 'plane':
            self.pose_names.add('depth_plane')
        self.gz = GzNode()
        if not self.gz.subscribe(Pose_V, '/world/person_eval/pose/info', self.receive_pose):
            raise RuntimeError('Cannot subscribe to Gazebo scene poses')
        for name, topic, encoding in [('rgb', RGB_TOPIC, 'bgr8'), ('depth', DEPTH_TOPIC, 'passthrough'),
                                      ('labels', LABEL_TOPIC, 'passthrough')]:
            self.create_subscription(Image, topic, self.image_callback(name, encoding), RGBD_QOS)
        self.create_subscription(CameraInfo, INFO_TOPIC, self.info, RGBD_QOS)
        self.create_subscription(Detection2DArray, DETECTION_TOPIC, self.boxes, 10)
        self.create_subscription(String, OUTPUT_TOPIC, self.output, 10)
        self.create_subscription(Clock, '/clock', self.clock, qos_profile_sensor_data)

    def store(self, stream, stamp, value):
        if self.start_ns <= stamp < self.stop_ns:
            self.data[stream][stamp] = value

    def image_callback(self, name, encoding):
        def receive(msg):
            stamp = stamp_ns(msg.header)
            if not self.start_ns <= stamp < self.stop_ns:
                return
            image = self.bridge.imgmsg_to_cv2(msg, desired_encoding=encoding)
            if name == 'labels' and image.ndim == 3:
                if not np.all(image == image[:, :, :1]):
                    raise RuntimeError('Expected grayscale semantic labels')
                image = image[:, :, 0]
            self.data[name][stamp] = (image, msg.header.frame_id, msg.encoding)
        return receive

    def info(self, msg):
        self.store('info', stamp_ns(msg.header), {'intrinsics': camera_intrinsics(msg),
                   'size': [msg.width, msg.height], 'frame_id': msg.header.frame_id})

    def boxes(self, msg):
        boxes = [{'bbox': box_xyxy(box.bbox), 'score': box.results[0].hypothesis.score}
                 for box in msg.detections]
        self.store('boxes', stamp_ns(msg.header), {'frame_id': msg.header.frame_id, 'boxes': boxes})

    def output(self, msg):
        data = json.loads(msg.data)
        self.store('output', data['stamp_ns'], data)

    def clock(self, msg):
        self.latest_clock = msg.clock.sec * 1_000_000_000 + msg.clock.nanosec

    def receive_pose(self, msg):
        stamp = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nsec
        if not self.start_ns - 50_000_000 <= stamp <= self.stop_ns + 50_000_000:
            return
        poses = {}
        if not self.poses:
            self.last_pose_names = sorted({pose.name for pose in msg.pose})
        for pose in msg.pose:
            if pose.name in self.pose_names:
                if pose.name in poses:
                    return
                p, q = pose.position, pose.orientation
                poses[pose.name] = [p.x, p.y, p.z, q.x, q.y, q.z, q.w]
        if poses.keys() == self.pose_names:
            with self.pose_lock:
                self.poses[stamp] = poses

    def record(self, case_id, expected_frames):
        data = self.data
        stamps = sorted(data['labels'])
        with self.pose_lock:
            poses = self.poses.copy()
        pose_stamps = sorted(poses)
        case_dir = ROOT / 'downloads/phase3/capture'
        case_dir.mkdir(parents=True, exist_ok=True)
        labels, images, depths, rows = [], [], [], []
        for stamp in stamps:
            label = data['labels'][stamp][0]
            rgb = data['rgb'].get(stamp)
            depth = data['depth'].get(stamp)
            labels.append(label)
            images.append(rgb[0] if rgb else np.zeros((*label.shape, 3), dtype=np.uint8))
            depths.append(depth[0] if depth else np.full(label.shape, np.nan, dtype=np.float32))
            index = bisect_left(pose_stamps, stamp)
            nearby = pose_stamps[max(0, index - 1):index + 1]
            pose_stamp = min(nearby, key=lambda value: abs(value - stamp)) if nearby else None
            rows.append({'stamp_ns': stamp, 'rgb_frame_id': rgb[1] if rgb else None,
                         'depth_frame_id': depth[1] if depth else None,
                         'depth_encoding': depth[2] if depth else None,
                         'info': data['info'].get(stamp), 'boxes': data['boxes'].get(stamp),
                         'output': data['output'].get(stamp), 'pose_stamp_ns': pose_stamp,
                         'poses': poses.get(pose_stamp)})
        subscribers = sorted({item.node_name for item in self.get_subscriptions_info_by_topic(LABEL_TOPIC)})
        topics = [topic for topic, _ in self.get_topic_names_and_types()]
        summary = {'case': case_id, 'expected_frames': expected_frames, 'frames': len(stamps),
                   'stream_counts': {key: len(value) for key, value in data.items()},
                   'pose_snapshots': len(poses), 'pose_entity_names': sorted(self.pose_names),
                   'observed_pose_names_if_missing': self.last_pose_names if not poses else [],
                   'truth_subscribers': subscribers,
                   'velocity_topics': [topic for topic in topics if 'cmd_vel' in topic]}
        print(json.dumps(summary), flush=True)
        if stamps:
            np.savez_compressed(case_dir / (case_id + '.npz'), labels=np.stack(labels),
                                rgb=np.stack(images), depth=np.stack(depths))
        (case_dir / (case_id + '.json')).write_text(json.dumps(dict(summary, rows=rows), allow_nan=False))
        minimum_frames = 100 if case_id.startswith('plane_') else expected_frames * 0.9
        if len(stamps) < minimum_frames or not poses or not data['output']:
            raise RuntimeError('Insufficient synchronized data. Inspect the capture summary and simulation log.')
        if subscribers != [self.get_name()] or summary['velocity_topics']:
            raise RuntimeError('The evaluation graph did not preserve truth isolation or stationary scope')


def run(case_id):
    config = load_settings(3)
    case = next(case for case in config['cases'] if case['id'] == case_id)
    duration = config['calibration_duration_sim_s'] if case['category'] == 'plane' else config['case_duration_sim_s']
    start = int(config['warmup_sim_s'] * 1e9)
    stop = start + int(duration * 1e9)
    rclpy.init()
    node = Capture(start, stop, case)
    try:
        deadline = time.monotonic() + 150
        drain_deadline = None
        while time.monotonic() < (drain_deadline or deadline):
            rclpy.spin_once(node, timeout_sec=0.05)
            if node.latest_clock >= stop and drain_deadline is None:
                drain_deadline = time.monotonic() + 2
        node.record(case_id, int(duration * config['sensor_hz']))
        if drain_deadline is None:
            raise RuntimeError('Simulation did not reach the end of the capture window')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('case')
    run(parser.parse_args().case)
