"""ROS interface for tracking, optional depth association and operator selection."""
from collections import OrderedDict
import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray

from person_depth_node import DETECTION_TOPIC, OUTPUT_TOPIC, box_xyxy, stamp_ns
from person_tracking import ByteTracker, TargetLock, observations_from_frame


TRACK_TOPIC = '/perception/people/tracks'
SELECT_TOPIC = '/perception/people/select_target'
DEPTH_WAIT_S = .15
INPUT_TIMEOUT_S = 1.25


class PersonTracking(Node):
    def __init__(self):
        super().__init__('person_tracking')
        self.use_depth = self.declare_parameter('use_depth', True).value
        self.tracker = ByteTracker(self.use_depth)
        self.lock = TargetLock(self.use_depth)
        self.pending, self.depth = OrderedDict(), OrderedDict()
        self.visible, self.observations = {}, []
        self.last_stamp = -1
        self.last_frame_wall = None
        self.frame_id = ''
        self.depth_paired = False
        self.publisher = self.create_publisher(String, TRACK_TOPIC, 10)
        self.create_subscription(Detection2DArray, DETECTION_TOPIC, self.receive_boxes, 20)
        if self.use_depth:
            self.create_subscription(String, OUTPUT_TOPIC, self.receive_depth, 20)
        self.create_subscription(String, SELECT_TOPIC, self.receive_selection, 10)
        self.create_timer(.025, self.tick)

    def receive_boxes(self, msg):
        stamp = stamp_ns(msg.header)
        if stamp <= self.last_stamp or stamp in self.pending:
            return
        boxes = [{'bbox': box_xyxy(det.bbox), 'score': det.results[0].hypothesis.score}
                 for det in msg.detections]
        self.pending[stamp] = (time.monotonic(), msg.header.frame_id, boxes)
        self.drain()

    def receive_depth(self, msg):
        frame = json.loads(msg.data)
        stamp = frame['stamp_ns']
        if stamp <= self.last_stamp:
            return
        self.depth[stamp] = frame
        while len(self.depth) > 32:
            self.depth.popitem(last=False)
        self.drain()

    def drain(self):
        while self.pending:
            stamp = min(self.pending)
            if stamp <= self.last_stamp:
                self.pending.pop(stamp)
                continue
            received, frame_id, boxes = self.pending[stamp]
            if self.use_depth and stamp not in self.depth and boxes and time.monotonic() - received < DEPTH_WAIT_S:
                break
            self.pending.pop(stamp)
            depth = self.depth.pop(stamp, None)
            if depth and depth['image_frame_id'] != frame_id:
                depth = None
            self.depth_paired = depth is not None
            self.observations = observations_from_frame(boxes, depth)
            self.last_stamp, self.frame_id, self.last_frame_wall = stamp, frame_id, time.monotonic()
            self.visible = self.tracker.update(self.observations, stamp)
            self.lock.update(stamp, self.visible, self.tracker.tracks, self.observations)
            self.publish('frame')

    def tick(self):
        self.drain()
        if self.last_frame_wall is not None and time.monotonic() - self.last_frame_wall > INPUT_TIMEOUT_S:
            prior = self.lock.state
            self.lock.expire()
            self.visible, self.observations = {}, []
            if self.lock.state != prior:
                self.publish('watchdog')

    def receive_selection(self, msg):
        try:
            request = json.loads(msg.data)
        except ValueError:
            return
        if not isinstance(request, dict) or request.get('session_id') != self.lock.session:
            return
        if request.get('track_id') is None and 'track_id' in request:
            self.lock.clear()
            self.publish('selection')
        elif (self.last_frame_wall is not None and time.monotonic() - self.last_frame_wall <= INPUT_TIMEOUT_S
              and self.lock.select(request['session_id'], request.get('track_id'), self.visible,
                                   self.last_stamp, self.observations)):
            self.publish('selection')
        else:
            self.get_logger().warning('Selection rejected. Choose a current, confirmed, unambiguous track.')

    def publish(self, event):
        tracks = [{'track_id': track.id, 'bbox': list(track.observation.box), 'score': track.observation.score,
                   'detection_index': track.observation.index, 'confirmed': track.hits >= 2,
                   'optical_xyz_m': track.observation.optical_xyz} for track in self.visible.values()]
        frame = {'stamp_ns': self.last_stamp, 'image_frame_id': self.frame_id, 'event': event,
                 'use_depth': self.use_depth, 'depth_paired': self.depth_paired, 'tracks': tracks,
                 **self.lock.report(self.visible)}
        self.publisher.publish(String(data=json.dumps(frame, allow_nan=False)))


if __name__ == '__main__':
    rclpy.init()
    node = PersonTracking()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
