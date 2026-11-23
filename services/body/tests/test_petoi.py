from unittest.mock import MagicMock, patch

import pytest

from tyapa_body.petoi import PetoiController, find_petoi_port


def _connected_controller() -> PetoiController:
    controller = PetoiController(port="/dev/ttyFAKE", baud=115200)
    controller.ser = MagicMock()
    controller.ser.is_open = True
    return controller


def _fake_port_info(device: str) -> MagicMock:
    info = MagicMock()
    info.device = device
    return info


def test_find_petoi_port_returns_device():
    fake_ser = MagicMock()
    with (
        patch(
            "tyapa_body.petoi.serial.tools.list_ports.comports",
            return_value=[_fake_port_info("/dev/ttyUSB0")],
        ),
        patch("tyapa_body.petoi.serial.Serial", return_value=fake_ser),
    ):
        result = find_petoi_port()
    assert result == "/dev/ttyUSB0"
    fake_ser.close.assert_called_once()


def test_find_petoi_port_raises_when_none_found():
    import serial as _serial

    with (
        patch(
            "tyapa_body.petoi.serial.tools.list_ports.comports",
            return_value=[_fake_port_info("/dev/ttyUSB0")],
        ),
        patch(
            "tyapa_body.petoi.serial.Serial",
            side_effect=_serial.SerialException("no device"),
        ),
    ):
        with pytest.raises(RuntimeError, match="No Petoi port found"):
            find_petoi_port()


def test_connect_autodiscovers_port():
    controller = PetoiController()
    assert controller.port is None
    mock_ser = MagicMock()
    mock_ser.is_open = True
    with (
        patch("tyapa_body.petoi.find_petoi_port", return_value="/dev/ttyUSB0") as mock_find,
        patch("tyapa_body.petoi.serial.Serial", return_value=mock_ser),
        patch("tyapa_body.petoi.time.sleep"),
    ):
        controller.connect()
        mock_find.assert_called_once()
    assert controller.port == "/dev/ttyUSB0"


def test_connect_opens_port_and_wakes():
    controller = PetoiController(port="/dev/ttyFAKE", baud=115200)
    mock_ser = MagicMock()
    mock_ser.is_open = True
    with (
        patch("tyapa_body.petoi.serial.Serial", return_value=mock_ser) as MockSerial,
        patch("tyapa_body.petoi.time.sleep"),
    ):
        controller.connect()
        MockSerial.assert_called_once_with("/dev/ttyFAKE", 115200, timeout=2)
    mock_ser.reset_input_buffer.assert_called_once()
    calls = [c.args[0] for c in mock_ser.write.call_args_list]
    assert b"\n" in calls
    assert b"kbalance\n" in calls


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
