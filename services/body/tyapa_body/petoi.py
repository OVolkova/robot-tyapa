import logging
import time

import serial
import serial.tools.list_ports

from tyapa_protocol.commands import PETOI_COMMANDS

from .base import RobotController
from .config import ROBOT_BAUD, ROBOT_WAKE_DELAY_S, STOP_ACTION

logger = logging.getLogger(__name__)


def find_petoi_port() -> str:
    for info in serial.tools.list_ports.comports():
        try:
            port = serial.Serial(info.device, ROBOT_BAUD, timeout=2)
            port.close()
            logger.info("Found Petoi on %s %s", info.device, info.name)
            return info.device
        except serial.SerialException:
            continue
    raise RuntimeError("No Petoi port found")


class PetoiController(RobotController):
    def __init__(self, port: str | None = None, baud: int = ROBOT_BAUD) -> None:
        self.port = port
        self.baud = baud
        self.ser: serial.Serial | None = None

    def connect(self) -> None:
        if self.port is None:
            self.port = find_petoi_port()
        self.ser = serial.Serial(self.port, self.baud, timeout=2)
        self.ser.write(b"\n")
        time.sleep(ROBOT_WAKE_DELAY_S)
        self.ser.reset_input_buffer()
        logger.info("Connected to Petoi on %s at %d baud", self.port, self.baud)
        self.execute_action(f"k{STOP_ACTION}")

    def execute_action(self, action: str) -> bool:
        """Send a skill (e.g. 'ksit'). True only if the command was written to the port."""
        cmd = self._resolve_command(action)
        if cmd is None:
            return False
        return self._write(cmd, "Serial")

    def send_raw(self, cmd: str) -> bool:
        return self._write(cmd, "Serial (raw)")

    def _write(self, cmd: str, label: str) -> bool:
        ser = self.ser
        if ser is None or not ser.is_open:
            logger.warning("Serial port not open; skipping %r", cmd)
            return False
        try:
            ser.write(f"{cmd}\n".encode("ascii"))
        except serial.SerialException as e:
            logger.error("Serial write failed: %s", e)
            return False
        logger.info("%s -> %r", label, cmd)
        return True

    def _resolve_command(self, action: str) -> str | None:
        if action.startswith("k"):
            skill_key = action[1:]
        else:
            logger.warning("Action %r missing 'k' prefix; prepending", action)
            skill_key = action
            action = f"k{action}"

        if skill_key not in PETOI_COMMANDS:
            logger.warning("Unknown skill %r — not in PETOI_COMMANDS; skipping", skill_key)
            return None

        return action
