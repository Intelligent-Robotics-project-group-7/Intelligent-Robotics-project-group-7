"""Measure actual virtual sensor traffic. Never creates a motion publisher."""
import argparse
import json
import pathlib
import time
import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, CameraInfo, LaserScan
from rosgraph_msgs.msg import Clock
from tf2_ros import Buffer, TransformListener


def stamp_s(stamp):
    return stamp.sec + stamp.nanosec * 1e-9


class Observer(Node):
    def __init__(self):
        super().__init__('step1_sensor_observer', parameter_overrides=[Parameter('use_sim_time', value=True)])
        self.bridge = CvBridge()
        self.frames, self.arrivals, self.source_stamps = {}, {}, {}
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.subscriptions_kept = []
        for name, topic, cls in [
            ('rgb', '/oakd/rgb/preview/image_raw', Image),
            ('depth', '/oakd/rgb/preview/depth', Image),
            ('camera_info', '/oakd/rgb/preview/camera_info', CameraInfo),
            ('scan', '/scan', LaserScan), ('clock', '/clock', Clock),
        ]:
            self.subscriptions_kept.append(self.create_subscription(
                cls, topic, lambda msg, key=name: self.receive(key, msg), qos_profile_sensor_data))

    def receive(self, key, msg):
        self.frames[key] = msg
        self.arrivals.setdefault(key, []).append(time.monotonic())
        stamp = msg.clock if key == 'clock' else msg.header.stamp
        self.source_stamps.setdefault(key, []).append(stamp_s(stamp))


parser = argparse.ArgumentParser()
parser.add_argument('--duration', type=float, default=45)
parser.add_argument('--output', default='/workspace/evidence')
args = parser.parse_args()
out = pathlib.Path(args.output)
out.mkdir(parents=True, exist_ok=True)
rclpy.init()
node = Observer()
print('Observer initialized; collecting stationary virtual sensors.', flush=True)
start = time.monotonic()
while time.monotonic() - start < args.duration:
    rclpy.spin_once(node, timeout_sec=0.1)

report = {'scope': 'stationary Gazebo virtual sensors only',
          'recorded_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'motion_commands_sent': False,
          'wall_observation_s': time.monotonic() - start, 'topics': node.get_topic_names_and_types(),
          'nodes': node.get_node_names(), 'streams': {}, 'checks': {}}
for key, stamps in node.arrivals.items():
    source = node.source_stamps[key]
    item = {'count': len(stamps), 'frame_id': getattr(getattr(node.frames[key], 'header', None), 'frame_id', None)}
    if len(stamps) > 1:
        item['wall_receive_hz'] = (len(stamps) - 1) / (stamps[-1] - stamps[0])
        item['source_time_span_s'] = source[-1] - source[0]
        if source[-1] > source[0]:
            item['sim_time_hz'] = (len(stamps) - 1) / (source[-1] - source[0])
            item['sim_to_wall_ratio_observed'] = (source[-1] - source[0]) / (stamps[-1] - stamps[0])
    report['streams'][key] = item
for key in ('rgb', 'depth', 'scan', 'clock'):
    report['checks'][key + '_messages'] = len(node.arrivals.get(key, [])) >= 5
report['checks']['camera_info_messages'] = 'camera_info' in node.frames

if 'rgb' in node.frames:
    msg = node.frames['rgb']
    rgb = node.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
    cv2.imwrite(str(out / 'camera_rgb.png'), rgb)
    report['streams']['rgb'].update(width=msg.width, height=msg.height, encoding=msg.encoding)
if 'depth' in node.frames:
    msg = node.frames['depth']
    depth = node.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough').astype(np.float32)
    if msg.encoding == '16UC1':
        depth *= 0.001
    elif msg.encoding != '32FC1':
        raise RuntimeError('Depth units not verified for encoding ' + msg.encoding)
    valid = np.isfinite(depth) & (depth > 0)
    center = depth[max(0, msg.height//2-5):msg.height//2+6,
                   max(0, msg.width//2-5):msg.width//2+6]
    center_valid = center[np.isfinite(center) & (center > 0)]
    report['streams']['depth'].update(
        width=msg.width, height=msg.height, encoding=msg.encoding,
        finite_positive_fraction=float(valid.mean()),
        center_roi_median_m=float(np.median(center_valid)) if center_valid.size else None,
        center_roi_definition='11x11 at image center; geometric plane, not a person')
    report['checks']['depth_has_valid_values'] = bool(valid.mean() > 0.1)
    visual = np.zeros_like(depth, dtype=np.uint8)
    visual[valid] = (np.clip(depth[valid], 0, 5) / 5 * 255).astype(np.uint8)
    colored = cv2.applyColorMap(visual, cv2.COLORMAP_TURBO)
    colored[~valid] = 0
    cv2.imwrite(str(out / 'camera_depth_0_to_5m.png'), colored)
if 'camera_info' in node.frames:
    info = node.frames['camera_info']
    report['camera_info'] = {'width': info.width, 'height': info.height,
                             'k': [float(x) for x in info.k], 'd': [float(x) for x in info.d],
                             'distortion_model': info.distortion_model}
    report['checks']['intrinsics_positive'] = bool(info.k[0] > 0 and info.k[4] > 0)
    report['checks']['image_dimensions_match_info'] = all(
        node.frames[k].width == info.width and node.frames[k].height == info.height
        for k in ('rgb', 'depth') if k in node.frames)
if 'rgb' in node.frames and 'depth' in node.frames:
    rgb_stamps = np.array(node.source_stamps['rgb'])
    depth_stamps = np.array(node.source_stamps['depth'])
    differences = np.array([np.min(np.abs(depth_stamps - t)) for t in rgb_stamps])
    report['rgb_nearest_depth_stamp_delta_ms'] = {
        'median': float(np.median(differences) * 1000),
        'p95': float(np.quantile(differences, .95) * 1000),
        'note': 'nearest stamp availability, not proof of matching exposure/calibration'}
camera_frame = getattr(getattr(node.frames.get('rgb'), 'header', None), 'frame_id', 'oakd_rgb_camera_optical_frame')
report['checks']['camera_transform_available'] = False
for base in ('base_link', 'base_footprint'):
    try:
        transform = node.buffer.lookup_transform(base, camera_frame, rclpy.time.Time())
        t, q = transform.transform.translation, transform.transform.rotation
        report['camera_to_base_transform'] = {'base': base, 'camera_frame': camera_frame,
                                             'translation': [t.x, t.y, t.z], 'quaternion_xyzw': [q.x, q.y, q.z, q.w]}
        report['checks']['camera_transform_available'] = True
        break
    except Exception as exc:
        report['tf_lookup_error'] = str(exc)
report['pass'] = all(report['checks'].values())
(out / 'sensor_smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2), flush=True)
node.destroy_node()
rclpy.shutdown()
raise SystemExit(0 if report['pass'] else 1)
