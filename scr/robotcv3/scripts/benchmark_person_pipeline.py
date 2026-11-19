"""Sequential replay benchmark of the ROS detection path, with Gazebo stopped."""
import argparse
import json
from pathlib import Path
import time
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray

ROOT = Path(__file__).resolve().parents[1]


class Probe(Node):
    def __init__(self):
        super().__init__('offline_detection_roundtrip_probe')
        self.publisher = self.create_publisher(Image, '/oakd/rgb/preview/image_raw', 10)
        self.receipts = {}
        self.subscription = self.create_subscription(Detection2DArray, '/perception/people/detections2d', self.receive, 10)

    def receive(self, msg):
        key = msg.header.stamp.sec*1_000_000_000 + msg.header.stamp.nanosec
        self.receipts[key] = time.perf_counter()


parser = argparse.ArgumentParser()
parser.add_argument('--samples', type=int, default=120)
args = parser.parse_args()
paths = []
for file in sorted((ROOT / 'evidence/phase2').glob('*/frames.json')):
    frames = json.loads(file.read_text())
    paths.extend(ROOT / row['image'] for row in frames[::3])
images = [cv2.imread(str(p)) for p in paths[:args.samples]]
if not images or any(img is None for img in images):
    raise RuntimeError('Replay input images are missing')
rclpy.init()
node = Probe()
bridge = CvBridge()
ready_deadline = time.monotonic()+20
while node.publisher.get_subscription_count() == 0 and time.monotonic() < ready_deadline:
    rclpy.spin_once(node, timeout_sec=.05)
if not node.publisher.get_subscription_count():
    raise RuntimeError('Detector has no RGB subscription')
latencies, timeouts = [], 0
for index, image in enumerate(images):
    message = bridge.cv2_to_imgmsg(image, encoding='bgr8')
    message.header.frame_id = 'oakd_rgb_camera_optical_frame'
    message.header.stamp.sec = 1000+index
    key = (1000+index)*1_000_000_000
    began = time.perf_counter()
    node.publisher.publish(message)
    while key not in node.receipts and time.perf_counter()-began < 2:
        rclpy.spin_once(node, timeout_sec=.005)
    if key in node.receipts:
        latencies.append((node.receipts[key]-began)*1000)
    else:
        timeouts += 1
# Separate warmup from measured steady replay, preserving timeout accounting.
measured = latencies[5:]
if not measured:
    raise RuntimeError('No replay detections returned')
report = {'mode': 'sequential one-in-flight ROS roundtrip, max_fps=0, two ONNX threads, no Gazebo',
          'scope': 'RGB publish to standard detection receipt; excludes PNG decode, message creation and sensor acquisition',
          'samples_requested': len(images), 'timeouts': timeouts, 'warmup_samples_excluded': 5,
          'measured_samples': len(measured),
          'p50_ms':float(np.percentile(measured,50)), 'p95_ms':float(np.percentile(measured,95)),
          'p99_ms':float(np.percentile(measured,99)),
          'reciprocal_mean_roundtrip_hz':float(1000/np.mean(measured)),
          'robot_motion_commands_sent':False}
(ROOT / 'evidence/phase2/offline_roundtrip.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
node.destroy_node()
rclpy.shutdown()
raise SystemExit(1 if timeouts else 0)
