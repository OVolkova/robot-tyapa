import time
from unittest.mock import MagicMock

import pytest

from tyapa_body import config
from tyapa_body.dry_run import DryRunRobot
from tyapa_body.service import Body, gait_limit, make_robot, raw_is_safe
from tyapa_protocol.commands import GAITS, PETOI_COMMANDS


def _body_with_mock_robot() -> Body:
    return Body(MagicMock())


def test_gait_set_only_contains_looping_gaits():
    assert "wkF" in GAITS
    assert "sit" not in GAITS
    assert "flip" not in GAITS  # trick, not a looping gait
    assert PETOI_COMMANDS.keys() >= GAITS


def test_make_robot_dry_run(monkeypatch):
    monkeypatch.setattr(config, "DRY_RUN", True)
    assert isinstance(make_robot(), DryRunRobot)


def test_dry_run_robot_accepts_everything():
    robot = DryRunRobot()
    robot.connect()
    assert robot.execute_action("ksit") is True
    assert robot.send_raw("m0 40") is True


def test_gait_limit_caps_at_config_default():
    assert gait_limit(None) == config.GAIT_MAX_S
    assert gait_limit(100) == config.GAIT_MAX_S  # requested longer than the cap
    assert gait_limit(1) == 1  # requested shorter than the cap


def test_on_act_unknown_action_errors_without_touching_robot():
    body = _body_with_mock_robot()
    reply = body.on_act({"action": "moonwalk"})
    assert reply["ok"] is False
    body.robot.execute_action.assert_not_called()


def test_on_act_valid_posture_sends_k_prefixed_command():
    body = _body_with_mock_robot()
    reply = body.on_act({"action": "sit"})
    assert reply["ok"] is True
    body.robot.execute_action.assert_called_once_with("ksit")
    assert body.stop_at is None  # postures don't get the gait watchdog


def test_on_act_gait_sets_a_stop_deadline():
    body = _body_with_mock_robot()
    body.on_act({"action": "wkF", "duration_s": 1.5})
    body.robot.execute_action.assert_called_once_with("kwkF")
    assert body.stop_at is not None
    assert 0 < body.stop_at - time.monotonic() <= 1.5


def test_on_raw_allows_joint_move():
    body = _body_with_mock_robot()
    reply = body.on_raw({"cmd": "m0 40"})
    assert reply["ok"] is True
    body.robot.send_raw.assert_called_once_with("m0 40")


def test_on_raw_rejects_a_skill_command():
    body = _body_with_mock_robot()
    reply = body.on_raw({"cmd": "kbf"})
    assert reply["ok"] is False
    body.robot.send_raw.assert_not_called()


def test_on_stop_clears_deadline_and_sends_stop_action():
    body = _body_with_mock_robot()
    body.stop_at = time.monotonic() + 5
    reply = body.on_stop({})
    assert reply["ok"] is True
    body.robot.execute_action.assert_called_once_with(f"k{config.STOP_ACTION}")
    assert body.stop_at is None


def test_tick_stops_the_gait_once_the_deadline_passes():
    body = _body_with_mock_robot()
    body.current = "wkF"
    body.stop_at = time.monotonic() - 0.01  # already due
    body.tick()
    body.robot.execute_action.assert_called_once_with(f"k{config.STOP_ACTION}")
    assert body.stop_at is None


def test_tick_does_nothing_before_the_deadline():
    body = _body_with_mock_robot()
    body.stop_at = time.monotonic() + 10
    body.tick()
    body.robot.execute_action.assert_not_called()


def test_on_act_bad_duration_errors_before_moving():
    body = _body_with_mock_robot()
    reply = body.on_act({"action": "wkF", "duration_s": "5"})
    assert reply["ok"] is False
    body.robot.execute_action.assert_not_called()
    assert body.current is None


def test_on_act_failed_write_reports_error_and_keeps_state():
    body = _body_with_mock_robot()
    body.robot.execute_action.return_value = False
    reply = body.on_act({"action": "sit"})
    assert reply["ok"] is False
    assert body.current is None


def test_on_raw_failed_write_reports_error():
    body = _body_with_mock_robot()
    body.robot.send_raw.return_value = False
    assert body.on_raw({"cmd": "m0 40"})["ok"] is False


def test_on_stop_failed_write_reports_error():
    body = _body_with_mock_robot()
    body.robot.execute_action.return_value = False
    assert body.on_stop({})["ok"] is False


@pytest.mark.parametrize("cmd", ["m0 40", "m0 30 8 -20", "m15 -125", "m0 125"])
def test_raw_is_safe_accepts_in_range_joint_moves(cmd):
    assert raw_is_safe(cmd)


@pytest.mark.parametrize(
    "cmd", ["m16 0", "m0 126", "m0 -126", "m0 30 99 5", "kbf", "m0", "m0 40; x"]
)
def test_raw_is_safe_rejects_out_of_range_or_malformed(cmd):
    assert not raw_is_safe(cmd)
