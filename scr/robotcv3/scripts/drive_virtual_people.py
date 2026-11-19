"""Move only named synthetic human meshes through Gazebo's scene pose service."""
import argparse
import json
import math
from pathlib import Path
import rclpy
from rclpy.node import Node as ROSNode
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from gz.transport13 import Node as GZNode
from gz.msgs10.pose_pb2 import Pose
from gz.msgs10.boolean_pb2 import Boolean


def interpolate(points, t):
    for a,b in zip(points, points[1:]):
        if t <= b[0]:
            fraction = max(0., min(1., (t-a[0])/(b[0]-a[0])))
            return [a[i]+fraction*(b[i]-a[i]) for i in (1,2,3)]
    return points[-1][1:]


class SceneDriver(ROSNode):
    def __init__(self, people):
        super().__init__('virtual_person_pose_driver')
        self.people, self.last_sim = people, -1.
        self.transport = GZNode()
        self.input = self.create_subscription(Clock, '/clock', self.update, qos_profile_sensor_data)

    def update(self, msg):
        t = msg.clock.sec + msg.clock.nanosec*1e-9
        if t < 1 or t-self.last_sim < .4:
            return
        self.last_sim = t
        for index, spec in enumerate(self.people, 1):
            x,y,yaw = interpolate(spec['waypoints'], t)
            pose = Pose()
            pose.name = f'person_{index}'
            pose.position.x, pose.position.y = x,y
            pose.orientation.z, pose.orientation.w = math.sin(yaw/2),math.cos(yaw/2)
            ok,response = self.transport.request('/world/person_eval/set_pose', pose, Pose, Boolean, 200)
            if not ok or not response.data:
                self.get_logger().warning('Virtual person pose update failed for ' + pose.name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('case')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cases = json.loads((root / 'config/person_scenarios.json').read_text())['cases']
    people = next(c['actors'] for c in cases if c['id'] == args.case)
    rclpy.init()
    node = SceneDriver(people)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
