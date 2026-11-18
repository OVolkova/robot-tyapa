import time
from unittest.mock import MagicMock

from tyapa_body import config
from tyapa_body.__main__ import Body, canonical, gait_limit, is_gait


def _body_with_mock_robot() -> Body:
    body = Body.__new__(Body)
    body.robot = MagicMock()
    body.current = None
    body.since = time.monotonic()
    body.stop_at = None
    return body


def test_canonical_accepts_known_key():
    assert canonical("sit") == "sit"
    assert canonical("wkR") == "wkR"  # literal key, no mirroring needed


def test_canonical_rejects_unknown_key():
    assert canonical("moonwalk") is None


def test_is_gait():
    assert is_gait("wkF") is True
    assert is_gait("sit") is False
    assert is_gait("flip") is False  # trick, not a looping gait


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
