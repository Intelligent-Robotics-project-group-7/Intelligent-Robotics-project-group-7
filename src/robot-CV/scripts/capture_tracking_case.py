"""Exercise the ROS target-selection interface and collect independent tracking truth."""
import argparse
import json
import time

from cv_bridge import CvBridge
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Image
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray

from capture_depth_case import LABEL_TOPIC
from evaluate_depth_suite import visible_boxes
from person_depth_node import DETECTION_TOPIC, OUTPUT_TOPIC, RGBD_QOS, box_xyxy, stamp_ns
from person_tracking_node import SELECT_TOPIC, TRACK_TOPIC
from score_tracking import CAPTURE, score


class Evaluation(Node):
    def __init__(self, case):
        super().__init__('phase4_tracking_evaluator')
        self.case = case
        self.bridge = CvBridge()
        self.latest_clock = 0
        self.last_request_ns = -1
        self.selected = False
        self.frames, self.truth, self.boxes, self.depth = {}, {}, {}, {}
        self.selection = self.create_publisher(String, SELECT_TOPIC, 10)
        self.create_subscription(Image, LABEL_TOPIC, self.receive_label, RGBD_QOS)
        self.create_subscription(Detection2DArray, DETECTION_TOPIC, self.receive_boxes, 20)
        self.create_subscription(String, OUTPUT_TOPIC, self.receive_depth, 20)
        self.create_subscription(String, TRACK_TOPIC, self.receive_tracks, 20)
        self.create_subscription(Clock, '/clock', self.receive_clock, qos_profile_sensor_data)

    def receive_label(self, msg):
        pixels = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')
        if pixels.ndim == 3:
            if not np.all(pixels == pixels[:, :, :1]):
                raise RuntimeError('Expected grayscale semantic labels')
            pixels = pixels[:, :, 0]
        self.truth[stamp_ns(msg.header)] = visible_boxes(pixels)

    def receive_boxes(self, msg):
        self.boxes[stamp_ns(msg.header)] = [
            {'bbox': box_xyxy(box.bbox), 'score': box.results[0].hypothesis.score} for box in msg.detections]

    def receive_depth(self, msg):
        value = json.loads(msg.data)
        self.depth[value['stamp_ns']] = value

    def receive_clock(self, msg):
        self.latest_clock = msg.clock.sec * 10**9 + msg.clock.nanosec

    def receive_tracks(self, msg):
        frame = json.loads(msg.data)
        stamp = frame['stamp_ns']
        if frame['selected_id'] is not None:
            self.selected = True
        if frame['event'] != 'frame':
            return
        self.frames[stamp] = frame
        if self.selected or not 2.2e9 <= stamp <= 4e9 or stamp <= self.last_request_ns:
            return
        confirmed = [track for track in frame['tracks'] if track['confirmed']]
        if len(confirmed) < (2 if self.case == 'two_crossing' else 1):
            return
        # The test operator selects the leftmost observed box. It never reads truth.
        target = min(confirmed, key=lambda track: track['bbox'][0] + track['bbox'][2])
        self.selection.publish(String(data=json.dumps({'session_id': frame['session_id'],
                                                       'track_id': target['track_id']})))
        self.last_request_ns = stamp

    def finish(self):
        stamps = sorted(stamp for stamp in self.truth if 2e9 <= stamp < 14e9)
        graph = {'truth_subscribers': sorted({item.node_name for item in
                                             self.get_subscriptions_info_by_topic(LABEL_TOPIC)}),
                 'velocity_topics': [name for name, _ in self.get_topic_names_and_types() if 'cmd_vel' in name]}
        if graph != {'truth_subscribers': [self.get_name()], 'velocity_topics': []}:
            raise RuntimeError('Truth isolation or stationary topic check failed')
        rows = [{'stamp_ns': stamp, 'truth': self.truth[stamp], 'frame': self.frames.get(stamp),
                 'boxes': self.boxes.get(stamp), 'depth': self.depth.get(stamp)} for stamp in stamps]
        expected, other = 11, None
        if self.case == 'two_crossing':
            # Use semantic labels only after collection to identify the left starting position.
            initial = next(row['truth'] for row in rows if len(row['truth']) == 2)
            expected, other = [item['label'] for item in sorted(initial, key=lambda item: item['box'][0])]
        report = score(rows, expected)
        if len(rows) < 54 or report['first_selection_ns'] is None:
            raise RuntimeError(f'Incomplete capture or target selection: {report}')
        if not report['target_outcomes'].get('correct_person'):
            raise RuntimeError(f'Initial selection did not produce target {expected}: {report}')
        path = CAPTURE / self.case / 'frames.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'selected_label': expected, 'other_label': other,
                                    'graph': graph, 'rows': rows}, allow_nan=False))
        print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('case')
    args = parser.parse_args()
    rclpy.init()
    node = Evaluation(args.case)
    try:
        deadline = time.monotonic() + 130
        drain_until = None
        while time.monotonic() < (drain_until or deadline):
            rclpy.spin_once(node, timeout_sec=.05)
            if drain_until is None and node.latest_clock >= 14_000_000_000:
                drain_until = time.monotonic() + 2
        if drain_until is None:
            raise RuntimeError('Simulator did not finish the tracking window')
        node.finish()
    finally:
        node.destroy_node()
        rclpy.shutdown()
