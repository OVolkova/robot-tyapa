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

    def execute_action(self, action: str) -> None:
        if not self._is_open():
            logger.warning("Serial port not open; skipping action %r", action)
            return
        cmd = self._resolve_command(action)
        if cmd is None:
            return
        try:
            self.ser.write(f"{cmd}\n".encode("ascii"))  # type: ignore[union-attr]
            logger.info("Serial -> %r", cmd)
        except serial.SerialException as e:
            logger.error("Serial write failed: %s", e)

    def send_raw(self, cmd: str) -> None:
        if not self._is_open():
            logger.warning("Serial port not open; skipping raw command %r", cmd)
            return
        try:
            self.ser.write(f"{cmd}\n".encode("ascii"))  # type: ignore[union-attr]
            logger.info("Serial (raw) -> %r", cmd)
        except serial.SerialException as e:
            logger.error("Serial write failed: %s", e)

    def _is_open(self) -> bool:
        return self.ser is not None and self.ser.is_open

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
