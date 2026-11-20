from concurrent.futures import Future
import importlib.util
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

if importlib.util.find_spec('rclpy') is None:
    raise unittest.SkipTest('Source the ROS 2 environment to run mission tests')

from action_msgs.msg import GoalStatus
from std_msgs.msg import Bool

from meg_navigation.mission import RescueMission


class MissionHarness:
    """Run mission callbacks without starting a ROS node or action servers."""

    set_state = RescueMission.set_state
    on_recorded = RescueMission.on_recorded
    request_cancel = RescueMission.request_cancel
    fail = RescueMission.fail
    start_undock = RescueMission.start_undock
    on_undock_accepted = RescueMission.on_undock_accepted
    on_undock_result = RescueMission.on_undock_result

    def __init__(self):
        self.state = 'WAIT_READY'
        self.recorded = False
        self.target = (2.0, 1.0)
        self.goal_handle = None
        self.cancel_requested = False
        self.undock_handle = None
        self.publish_status = Mock()
        self.get_logger = Mock()
        self.undock_client = Mock()
        self.undock_client.server_is_ready.return_value = True
        self.acceptance = self.undock_client.send_goal_async.return_value = Future()
        self.result = Future()
        self.undock_goal = Mock(accepted=True)
        self.undock_goal.get_result_async.return_value = self.result


class MissionTests(unittest.TestCase):
    def test_recording_ack_after_arrival_only(self):
        mission = MissionHarness()
        mission.state = 'APPROACHING'
        mission.on_recorded(Bool(data=True))
        self.assertFalse(mission.recorded)
        mission.set_state('WAIT_RECORDING', 'Arrived')
        mission.on_recorded(Bool(data=False))
        self.assertFalse(mission.recorded)
        mission.on_recorded(Bool(data=True))
        self.assertTrue(mission.recorded)

    def test_undock_success_with_already_completed_futures(self):
        mission = MissionHarness()
        mission.acceptance.set_result(mission.undock_goal)
        mission.result.set_result(SimpleNamespace(status=GoalStatus.STATUS_SUCCEEDED))
        mission.start_undock()
        self.assertEqual(mission.state, 'CAPTURE_BASE')
        self.assertIsNone(mission.undock_handle)
        mission.undock_goal.cancel_goal_async.assert_not_called()

    def test_timeout_cancels_accepted_undock_and_ignores_late_result(self):
        mission = MissionHarness()
        mission.start_undock()
        mission.acceptance.set_result(mission.undock_goal)
        mission.fail('Mission timed out')
        mission.undock_goal.cancel_goal_async.assert_called_once_with()
        mission.result.set_result(SimpleNamespace(status=GoalStatus.STATUS_SUCCEEDED))
        self.assertEqual(mission.state, 'FAILED')
        self.assertIsNone(mission.undock_handle)
        mission.publish_status.assert_called_with('Mission timed out')

    def test_timeout_cancels_undock_accepted_after_failure(self):
        mission = MissionHarness()
        mission.start_undock()
        mission.fail('Mission timed out')
        mission.acceptance.set_result(mission.undock_goal)
        mission.undock_goal.cancel_goal_async.assert_called_once_with()
        mission.undock_goal.get_result_async.assert_not_called()
        self.assertEqual(mission.state, 'FAILED')
        mission.publish_status.assert_called_with('Mission timed out')
