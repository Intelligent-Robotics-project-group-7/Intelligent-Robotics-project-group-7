"""Evaluate exact-stamp RGB/prediction/independent renderer truth, without motion."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
from rosgraph_msgs.msg import Clock
from vision_msgs.msg import Detection2DArray
from detection_metrics import match_frame, summarize

ROOT = Path(__file__).resolve().parents[1]


def stamp_ns(stamp):
    return int(stamp.sec)*1_000_000_000 + int(stamp.nanosec)


def xyxy(cx, cy, width, height):
    return [float(cx-width/2), float(cy-height/2), float(cx+width/2), float(cy+height/2)]


class Collector(Node):
    def __init__(self):
        super().__init__('phase2_independent_evaluator', parameter_overrides=[Parameter('use_sim_time', value=True)])
        self.images, self.truth, self.predictions, self.arrivals, self.masks = {}, {}, {}, {}, {}
        self.latest_clock = 0
        self.bridge = CvBridge()
        self.subs = [
            self.create_subscription(Image, '/oakd/rgb/preview/image_raw', self.image, qos_profile_sensor_data),
            self.create_subscription(Image, '/evaluation/semantic/labels_map', self.labels, qos_profile_sensor_data),
            self.create_subscription(Detection2DArray, '/perception/people/detections2d', self.detections, 10),
            self.create_subscription(Clock, '/clock', self.clock, qos_profile_sensor_data),
        ]

    def image(self, msg):
        stamp = stamp_ns(msg.header.stamp)
        self.images[stamp] = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        self.arrivals.setdefault(stamp, {})['rgb'] = time.monotonic()

    def labels(self, msg):
        pixels = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')
        if pixels.ndim == 3:
            if not (np.array_equal(pixels[:,:,0], pixels[:,:,1]) and np.array_equal(pixels[:,:,0], pixels[:,:,2])):
                raise RuntimeError('Semantic labels_map channels disagree with documented grayscale label encoding')
            pixels = pixels[:,:,0]
        boxes = []
        for label in (11, 12):
            ys, xs = np.where(pixels == label)
            if xs.size == 0:
                continue
            boxes.append({'label': str(label), 'box': [float(xs.min()), float(ys.min()),
                          float(xs.max()+1), float(ys.max()+1)], 'visible_pixels': int(xs.size)})
        stamp = stamp_ns(msg.header.stamp)
        self.truth[stamp] = boxes
        self.masks[stamp] = pixels

    def detections(self, msg):
        stamp = stamp_ns(msg.header.stamp)
        self.predictions[stamp] = [
            {'box': xyxy(d.bbox.center.position.x, d.bbox.center.position.y, d.bbox.size_x, d.bbox.size_y),
             'score': float(d.results[0].hypothesis.score), 'class_name': d.results[0].hypothesis.class_id}
            for d in msg.detections if d.results and d.results[0].hypothesis.class_id == 'person'
            and d.results[0].hypothesis.score >= .25]
        self.arrivals.setdefault(stamp, {})['prediction'] = time.monotonic()

    def clock(self, msg):
        self.latest_clock = stamp_ns(msg.clock)


def run(case_id, max_wall):
    settings = json.loads((ROOT / 'config/person_scenarios.json').read_text())
    start_ns = int(settings['warmup_sim_s'] * 1e9)
    stop_ns = int((settings['warmup_sim_s'] + settings['case_duration_sim_s']) * 1e9)
    output = ROOT / 'evidence/phase2' / case_id
    output.mkdir(parents=True, exist_ok=True)
    dataset = ROOT / 'downloads/phase2/dataset' / case_id
    dataset.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    node = Collector()
    began = time.monotonic()
    reached = None
    next_progress = began + 10
    while time.monotonic()-began < max_wall:
        rclpy.spin_once(node, timeout_sec=.05)
        if time.monotonic() >= next_progress:
            print(json.dumps({'progress': case_id, 'sim_s': node.latest_clock/1e9,
                              'rgb': len(node.images), 'truth': len(node.truth),
                              'predictions': len(node.predictions)}), flush=True)
            next_progress += 10
        if node.latest_clock >= stop_ns and reached is None:
            reached = time.monotonic()
        if reached is not None and time.monotonic()-reached >= 2:
            break
    rows = []
    stamps = sorted(t for t in node.images if start_ns <= t < stop_ns and t in node.truth)
    if not stamps:
        debug = {'rgb_messages': len(node.images), 'truth_messages': len(node.truth),
                 'prediction_messages': len(node.predictions), 'clock_ns': node.latest_clock,
                 'topics': node.get_topic_names_and_types()}
        (output / 'failed_collection.json').write_text(json.dumps(debug, indent=2))
        raise RuntimeError('No exact-stamp RGB/truth pairs; refusing to fabricate ground truth')
    sample_indices = {0, len(stamps)//3, 2*len(stamps)//3, len(stamps)-1}
    for i, stamp in enumerate(stamps):
        image = node.images[stamp]
        predictions = node.predictions.get(stamp, [])
        labels = node.truth[stamp]
        arrivals = node.arrivals.get(stamp, {})
        delay = (arrivals['prediction']-arrivals['rgb'])*1000 if 'prediction' in arrivals and 'rgb' in arrivals else None
        filename = dataset / (str(stamp) + '.png')
        cv2.imwrite(str(filename), image)
        row = {'stamp_ns': stamp, 'image': filename.relative_to(ROOT).as_posix(),
               'image_sha256': hashlib.file_digest(filename.open('rb'), 'sha256').hexdigest(),
               'ground_truth': labels, 'predictions': predictions,
               'prediction_message_received': stamp in node.predictions,
               'subscriber_rgb_to_prediction_ms': delay,
               'matching': match_frame(labels, predictions, settings['evaluation_iou'])}
        rows.append(row)
        if i in sample_indices:
            cv2.imwrite(str(output / f'labels_{i:03d}.png'), node.masks[stamp])
            display = image.copy()
            for entry in labels:
                x1,y1,x2,y2=map(round,entry['box']); cv2.rectangle(display,(x1,y1),(x2,y2),(255,180,0),1)
            for entry in predictions:
                x1,y1,x2,y2=map(round,entry['box']); cv2.rectangle(display,(x1,y1),(x2,y2),(0,220,0),1)
                cv2.putText(display, f"person {entry['score']:.2f}", (x1,max(12,y1-3)), cv2.FONT_HERSHEY_SIMPLEX,.35,(0,220,0),1)
            cv2.putText(display, case_id, (4,15), cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,255),1)
            cv2.imwrite(str(output / f'example_{i:03d}.png'), display)
    summary = summarize(rows)
    delays = [r['subscriber_rgb_to_prediction_ms'] for r in rows if r['subscriber_rgb_to_prediction_ms'] is not None]
    timing = {key: float(np.percentile(delays, p)) for key,p in [('p50_ms',50),('p95_ms',95),('p99_ms',99)]} if delays else None
    summary.update(case=case_id, collection_wall_s=time.monotonic()-began,
                   simulation_completed=reached is not None,
                   rgb_messages_total=len(node.images), truth_messages_total=len(node.truth),
                   prediction_messages_total=len(node.predictions),
                   paired_rgb_truth_frames=len(rows),
                   prediction_coverage=sum(r['prediction_message_received'] for r in rows)/len(rows),
                   subscriber_receipt_latency=timing,
                   iou_threshold=settings['evaluation_iou'], score_threshold=.25,
                   annotation='Visible-pixel boxes from Gazebo semantic labels 11/12; separate co-located sensor',
                   motion_commands_sent=False, motion_command_scope='robot base; synthetic person pose updates are enabled',
                   tracking_enabled=False,
                   recorded_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    (output / 'frames.json').write_text(json.dumps(rows, indent=2) + '\n')
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)
    node.destroy_node()
    rclpy.shutdown()
    return 0 if summary['simulation_completed'] and summary['prediction_messages_total'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('case')
    parser.add_argument('--max-wall', type=float, default=100)
    args = parser.parse_args()
    raise SystemExit(run(args.case, args.max_wall))
