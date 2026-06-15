from unittest.mock import MagicMock, patch

from robot_tyapa.robot.petoi import PetoiController


def _connected_controller() -> PetoiController:
    controller = PetoiController(port="/dev/ttyFAKE", baud=115200)
    controller.ser = MagicMock()
    controller.ser.is_open = True
    return controller


def test_connect_opens_port_and_wakes():
    controller = PetoiController(port="/dev/ttyFAKE", baud=115200)
    mock_ser = MagicMock()
    mock_ser.is_open = True
    with (
        patch("robot_tyapa.robot.petoi.serial.Serial", return_value=mock_ser) as MockSerial,
        patch("robot_tyapa.robot.petoi.time.sleep"),
    ):
        controller.connect()
        MockSerial.assert_called_once_with("/dev/ttyFAKE", 115200, timeout=2)
    mock_ser.write.assert_called_once_with(b"\n")
    mock_ser.reset_input_buffer.assert_called_once()


def test_execute_valid_action_sends_command():
    c = _connected_controller()
    c.execute_action("ksit")
    c.ser.write.assert_called_once_with(b"ksit\n")


def test_execute_valid_gait_sends_command():
    c = _connected_controller()
    c.execute_action("kwkF")
    c.ser.write.assert_called_once_with(b"kwkF\n")


def test_execute_unknown_action_skips(caplog):
    c = _connected_controller()
    c.execute_action("kzzzzzunknown")
    c.ser.write.assert_not_called()
    assert "Unknown skill" in caplog.text


def test_execute_action_without_k_prefix_prepends_and_validates(caplog):
    c = _connected_controller()
    c.execute_action("sit")  # bare name — should become "ksit"
    c.ser.write.assert_called_once_with(b"ksit\n")


def test_execute_action_when_port_closed_skips(caplog):
    c = PetoiController()
    c.ser = MagicMock()
    c.ser.is_open = False
    c.execute_action("ksit")
    c.ser.write.assert_not_called()
    assert "not open" in caplog.text


def test_disconnect_closes_port():
    c = _connected_controller()
    c.disconnect()
    c.ser.close.assert_called_once()


def test_resolve_command_passes_through_k_prefix():
    c = PetoiController()
    assert c._resolve_command("kwkF") == "kwkF"


def test_resolve_command_returns_none_for_unknown_key(caplog):
    c = PetoiController()
    result = c._resolve_command("knotacommand")
    assert result is None
    assert "Unknown skill" in caplog.text


def test_execute_action_serial_exception_logs_error(caplog):
    import serial

    c = _connected_controller()
    c.ser.write.side_effect = serial.SerialException("boom")
    c.execute_action("ksit")
    assert "Serial write failed" in caplog.text


def test_get_state_returns_readline():
    c = _connected_controller()
    c.ser.readline.return_value = b"v1.0\n"
    result = c.get_state()
    c.ser.write.assert_called_once_with(b"v\n")
    assert result == "v1.0"


def test_get_state_when_port_closed_returns_empty():
    c = PetoiController()
    c.ser = MagicMock()
    c.ser.is_open = False
    assert c.get_state() == ""


def test_get_state_serial_exception_returns_empty(caplog):
    import serial

    c = _connected_controller()
    c.ser.write.side_effect = serial.SerialException("read error")
    assert c.get_state() == ""
    assert "Serial read failed" in caplog.text
