"""Explore an unknown map, approach a reported marker, and return to base.

Nav2 owns path following and velocity output. This node only chooses goals and
uses the NavigateToPose action; it never publishes cmd_vel.
"""

import math
import time

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PointStamped, PoseStamped
from irobot_create_msgs.action import Undock
from irobot_create_msgs.msg import DockStatus
from lifecycle_msgs.msg import State
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import OccupancyGrid
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from std_msgs.msg import Bool, String
from tf2_ros import Buffer, TransformException, TransformListener

from meg_navigation.grid import Grid, choose_approach_goal, choose_frontier_goal


def yaw_from_quaternion(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y),
                      1 - 2 * (q.y * q.y + q.z * q.z))


def make_pose(clock, x, y, yaw):
    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.header.stamp = clock.now().to_msg()
    pose.pose.position.x = x
    pose.pose.position.y = y
    pose.pose.orientation.z = math.sin(yaw / 2)
    pose.pose.orientation.w = math.cos(yaw / 2)
    return pose


class RescueMission(Node):
    def __init__(self):
        super().__init__('meg_rescue_mission')
        self.declare_parameter('goal_timeout_s', 120.0)
        self.declare_parameter('mission_timeout_s', 900.0)
        self.declare_parameter('stop_distance_m', 0.8)
        self.declare_parameter('clearance_m', 0.20)
        self.declare_parameter('max_goal_retries', 2)
        self.declare_parameter('require_recording_ack', True)
        self.declare_parameter('recording_timeout_s', 60.0)
        self.declare_parameter('require_dock_status', True)
        self.declare_parameter('map_ready_timeout_s', 120.0)
        self.declare_parameter('frontier_wait_s', 60.0)
        self.declare_parameter('approach_map_wait_s', 180.0)

        map_qos = QoSProfile(depth=1)
        map_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
        map_qos.reliability = ReliabilityPolicy.RELIABLE
        dock_qos = QoSProfile(depth=10)
        dock_qos.reliability = ReliabilityPolicy.BEST_EFFORT

        self.create_subscription(OccupancyGrid, '/map', self.on_map, map_qos)
        self.create_subscription(PointStamped, '/rescue_target', self.on_target, 10)
        self.create_subscription(Bool, '/rescue_recorded', self.on_recorded, 10)
        self.create_subscription(DockStatus, '/dock_status', self.on_dock, dock_qos)
        self.status_pub = self.create_publisher(String, '/meg_navigation/status', 10)
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.nav_state_client = self.create_client(GetState, '/bt_navigator/get_state')
        self.nav_state_future = None
        self.nav_active = False
        self.undock_client = ActionClient(self, Undock, 'undock')
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.grid = None
        self.map_revision = 0
        self.approach_checked_revision = -1
        self.target = None
        self.target_received_at = None
        self.recorded = False
        self.docked = None
        self.undock_handle = None
        self.base_pose = None
        self.exclusions = []
        self.goal_handle = None
        self.goal_send_pending = False
        self.goal_kind = None
        self.goal_xy = None
        self.goal_started = None
        self.cancel_requested = False
        self.retries = {'approach': 0, 'return': 0}
        self.started = time.monotonic()
        self.state = 'WAIT_READY'
        self.state_since = self.started
        self.last_status = None
        self.timer = self.create_timer(0.5, self.tick)
        self.publish_status('Waiting for a usable map and Nav2')

    def publish_status(self, detail):
        status = f'{self.state}: {detail}'
        if status != self.last_status:
            self.status_pub.publish(String(data=status))
            self.get_logger().info(status)
            self.last_status = status

    def set_state(self, state, detail):
        self.state = state
        self.state_since = time.monotonic()
        self.publish_status(detail)

    def on_map(self, message):
        q = message.info.origin.orientation
        try:
            self.grid = Grid(
                width=message.info.width,
                height=message.info.height,
                resolution=message.info.resolution,
                origin_x=message.info.origin.position.x,
                origin_y=message.info.origin.position.y,
                origin_yaw=yaw_from_quaternion(q),
                data=tuple(message.data),
            )
            self.map_revision += 1
        except ValueError as error:
            self.get_logger().warn(f'Ignoring invalid map: {error}')

    def on_target(self, message):
        if self.target is not None:
            return
        if message.header.frame_id != 'map':
            self.get_logger().warn('Ignoring /rescue_target outside the map frame')
            return
        if not all(math.isfinite(value) for value in
                   (message.point.x, message.point.y)):
            self.get_logger().warn('Ignoring non-finite rescue target')
            return
        self.target = (message.point.x, message.point.y)
        self.target_received_at = time.monotonic()
        self.approach_checked_revision = -1
        self.get_logger().info(f'Rescue target received at {self.target}')

    def on_dock(self, message):
        self.docked = message.is_docked

    def on_recorded(self, message):
        if self.state == 'WAIT_RECORDING' and message.data:
            self.recorded = True

    def robot_xy(self):
        try:
            transform = self.tf_buffer.lookup_transform('map', 'base_link', Time())
        except TransformException:
            return None
        return (transform.transform.translation.x,
                transform.transform.translation.y)

    def nav2_is_active(self):
        if self.nav_active:
            return True
        if self.nav_state_future is not None:
            if not self.nav_state_future.done():
                return False
            try:
                result = self.nav_state_future.result()
                self.nav_active = (result.current_state.id ==
                                   State.PRIMARY_STATE_ACTIVE)
            except Exception as error:
                self.get_logger().warn(f'Nav2 lifecycle check failed: {error}')
            self.nav_state_future = None
            return self.nav_active
        if self.nav_state_client.service_is_ready():
            self.nav_state_future = self.nav_state_client.call_async(GetState.Request())
        return False

    def request_cancel(self, handle, action):
        try:
            handle.cancel_goal_async()
        except Exception as error:
            self.get_logger().warn(f'Failed to request cancellation of {action}: {error}')

    def fail(self, reason):
        if self.state in ('DONE', 'FAILED'):
            return
        self.set_state('FAILED', reason)
        if self.goal_handle is not None and not self.cancel_requested:
            self.cancel_requested = True
            self.request_cancel(self.goal_handle, 'navigation')
        if self.undock_handle is not None:
            self.request_cancel(self.undock_handle, 'undock')

    def start_undock(self):
        if not self.undock_client.server_is_ready():
            self.fail('Robot is docked but the undock action is unavailable')
            return
        self.set_state('UNDOCKING', 'Undocking before navigation')
        try:
            future = self.undock_client.send_goal_async(Undock.Goal())
        except Exception as error:
            self.fail(f'Undock request failed: {error}')
            return
        future.add_done_callback(self.on_undock_accepted)

    def on_undock_accepted(self, future):
        try:
            handle = future.result()
        except Exception as error:
            self.fail(f'Undock request failed: {error}')
            return
        if self.state != 'UNDOCKING':
            if handle.accepted:
                self.request_cancel(handle, 'undock')
            return
        if not handle.accepted:
            self.fail('Undock goal was rejected')
            return
        self.undock_handle = handle
        try:
            result_future = handle.get_result_async()
        except Exception as error:
            self.fail(f'Could not wait for undocking: {error}')
            return
        result_future.add_done_callback(self.on_undock_result)

    def on_undock_result(self, future):
        if self.state != 'UNDOCKING':
            self.undock_handle = None
            return
        try:
            status = future.result().status
        except Exception as error:
            self.fail(f'Undock result failed: {error}')
            return
        self.undock_handle = None
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.set_state('CAPTURE_BASE', 'Recording a reachable return pose')
        else:
            self.fail(f'Undock ended with status {status}')

    def send_nav_goal(self, kind, pose):
        if self.goal_send_pending or self.goal_handle is not None:
            return
        request = NavigateToPose.Goal()
        request.pose = pose
        self.goal_kind = kind
        self.goal_xy = (pose.pose.position.x, pose.pose.position.y)
        self.goal_started = time.monotonic()
        self.goal_send_pending = True
        future = self.nav_client.send_goal_async(request)
        future.add_done_callback(self.on_nav_accepted)
        self.publish_status(f'Sending {kind} goal at {self.goal_xy}')

    def on_nav_accepted(self, future):
        self.goal_send_pending = False
        try:
            handle = future.result()
        except Exception as error:
            self.finish_nav(False, f'Goal request failed: {error}')
            return
        if not handle.accepted:
            self.finish_nav(False, 'Nav2 rejected the goal')
            return
        self.goal_handle = handle
        handle.get_result_async().add_done_callback(self.on_nav_result)
        if self.state == 'FAILED':
            # A late acceptance must not drive after the mission timed out.
            self.cancel_requested = True
            self.request_cancel(handle, 'navigation')

    def on_nav_result(self, future):
        try:
            result = future.result()
            self.finish_nav(result.status == GoalStatus.STATUS_SUCCEEDED,
                            f'Nav2 status {result.status}')
        except Exception as error:
            self.finish_nav(False, f'Nav2 result failed: {error}')

    def finish_nav(self, success, detail):
        kind, xy = self.goal_kind, self.goal_xy
        self.goal_handle = None
        self.goal_send_pending = False
        self.goal_kind = None
        self.goal_xy = None
        self.goal_started = None
        self.cancel_requested = False
        if self.state == 'FAILED':
            return
        if kind == 'explore':
            if xy is not None and (success or detail.startswith('Nav2 status ')):
                self.exclusions.append(xy)
            if self.target is not None:
                self.set_state('EXPLORING',
                               f'Target sighted; mapping a safe approach: {detail}')
            else:
                self.set_state('EXPLORING', f'Exploration goal finished: {detail}')
        elif kind == 'approach':
            if success:
                if self.get_parameter('require_recording_ack').value:
                    self.set_state('WAIT_RECORDING',
                                   'Target approached; waiting for saved position and image')
                else:
                    self.set_state('RETURN_PENDING', 'Target approached; returning to base')
            elif self.retries['approach'] < self.get_parameter('max_goal_retries').value:
                self.retries['approach'] += 1
                self.set_state('APPROACH_PENDING', f'Retrying approach: {detail}')
            else:
                self.fail(f'Approach failed: {detail}')
        elif kind == 'return':
            if success:
                self.set_state('DONE', 'Returned to base pose')
            elif self.retries['return'] < self.get_parameter('max_goal_retries').value:
                self.retries['return'] += 1
                self.set_state('RETURN_PENDING', f'Retrying return: {detail}')
            else:
                self.fail(f'Return failed: {detail}')

    def tick(self):
        if self.state in ('DONE', 'FAILED'):
            return
        if time.monotonic() - self.started > self.get_parameter('mission_timeout_s').value:
            self.fail('Mission timed out')
            return
        if (self.goal_started is not None and self.goal_handle is not None
                and not self.cancel_requested
                and time.monotonic() - self.goal_started >
                self.get_parameter('goal_timeout_s').value):
            self.get_logger().warn('Navigation goal timed out; cancelling')
            self.cancel_requested = True
            self.request_cancel(self.goal_handle, 'navigation')

        if self.state == 'WAIT_READY':
            if (self.grid is None or
                    not any(0 <= value <= self.grid.free_threshold
                            for value in self.grid.data)):
                if (time.monotonic() - self.state_since >
                        self.get_parameter('map_ready_timeout_s').value):
                    self.fail('Map has no known free cells; check SLAM and /scan')
                return
            if (not self.nav_client.server_is_ready() or
                    not self.nav2_is_active()):
                return
            if not self.get_parameter('require_dock_status').value:
                self.set_state('CAPTURE_BASE', 'Recording a reachable return pose')
                return
            if self.docked is None:
                return
            if self.docked:
                self.start_undock()
            else:
                self.set_state('CAPTURE_BASE', 'Recording a reachable return pose')
            return

        if self.state == 'CAPTURE_BASE':
            xy = self.robot_xy()
            if xy is None:
                return
            self.base_pose = make_pose(self.get_clock(), xy[0], xy[1], 0.0)
            self.set_state('EXPLORING', 'Starting frontier exploration')
            return

        if self.state == 'EXPLORING':
            if self.goal_handle is not None or self.goal_send_pending:
                return
            xy = self.robot_xy()
            if xy is None:
                return
            if self.target is not None:
                if (time.monotonic() - self.target_received_at >
                        self.get_parameter('approach_map_wait_s').value):
                    self.fail('Target sighted but no mapped approach route was found')
                    return
                if self.map_revision != self.approach_checked_revision:
                    approach = choose_approach_goal(
                        self.grid, self.grid.world_to_cell(*xy), *self.target,
                        stop_distance_m=self.get_parameter('stop_distance_m').value,
                        clearance_m=self.get_parameter('clearance_m').value)
                    self.approach_checked_revision = self.map_revision
                    if approach is not None:
                        self.set_state('APPROACH_PENDING',
                                       'Target located; mapped approach route is ready')
                        return
            goal = choose_frontier_goal(
                self.grid, self.grid.world_to_cell(*xy), self.exclusions,
                clearance_m=self.get_parameter('clearance_m').value,
                min_travel_m=0.2 if self.target is not None else 0.5,
                preferred_target=self.target)
            if goal is None:
                # The map may still be growing after an earlier arrival.
                if (time.monotonic() - self.state_since >
                        self.get_parameter('frontier_wait_s').value):
                    self.fail('No reachable frontier or mapped approach route')
                return
            self.send_nav_goal('explore', make_pose(self.get_clock(), goal.x, goal.y, goal.yaw))
            return

        if self.state == 'APPROACH_PENDING':
            if self.grid is None or self.target is None:
                return
            xy = self.robot_xy()
            if xy is None:
                return
            goal = choose_approach_goal(
                self.grid, self.grid.world_to_cell(*xy), *self.target,
                stop_distance_m=self.get_parameter('stop_distance_m').value,
                clearance_m=self.get_parameter('clearance_m').value)
            if goal is None:
                if (time.monotonic() - self.target_received_at <
                        self.get_parameter('approach_map_wait_s').value):
                    self.set_state('EXPLORING',
                                   'Target sighted; exploring for a mapped approach')
                    return
                self.fail('No reachable pose at the requested marker stopping distance')
                return
            self.set_state('APPROACHING', 'Moving to a safe marker standoff pose')
            self.send_nav_goal('approach', make_pose(self.get_clock(), goal.x, goal.y, goal.yaw))
            return

        if self.state == 'RETURN_PENDING':
            if self.base_pose is None:
                self.fail('Base pose was not recorded')
                return
            self.base_pose.header.stamp = self.get_clock().now().to_msg()
            self.set_state('RETURNING', 'Navigating back to base')
            self.send_nav_goal('return', self.base_pose)

        if self.state == 'WAIT_RECORDING':
            if self.recorded:
                self.set_state('RETURN_PENDING', 'Recording confirmed; returning to base')
            elif (time.monotonic() - self.state_since >
                  self.get_parameter('recording_timeout_s').value):
                self.fail('Timed out waiting for /rescue_recorded')


def main(args=None):
    rclpy.init(args=args)
    node = RescueMission()
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
