"""Body service: the only program that talks to the ESP32."""

import logging
import re
import time

from tyapa_protocol import endpoints as ep
from tyapa_protocol import messages as m
from tyapa_protocol import setup_logging
from tyapa_protocol.commands import GAITS, PETOI_COMMANDS
from tyapa_protocol.transport import Server

from . import config
from .base import RobotController
from .dry_run import DryRunRobot

logger = logging.getLogger(__name__)

# Raw joint moves the brain may send, e.g. "m0 40" or "m0 30 8 -20". Nothing else raw.
RAW_OK = re.compile(r"^m\d{1,2} -?\d{1,3}( \d{1,2} -?\d{1,3})*$")


def raw_is_safe(cmd: str) -> bool:
    """A joint move ("m0 40", "m0 30 8 -20") whose joints and angles are within servo range."""
    if not RAW_OK.match(cmd):
        return False
    numbers = [int(x) for x in cmd[1:].split()]
    joints, angles = numbers[0::2], numbers[1::2]
    return all(0 <= j <= config.MAX_JOINT for j in joints) and all(
        abs(a) <= config.MAX_ANGLE for a in angles
    )


def gait_limit(requested: float | None) -> float | None:
    caps = [x for x in (requested, config.GAIT_MAX_S) if x and x > 0]
    return min(caps) if caps else None


def make_robot() -> RobotController:
    """The real Petoi, or a logging stand-in when BODY_DRY_RUN=1. Imports pyserial lazily."""
    if config.DRY_RUN:
        return DryRunRobot()
    from .petoi import PetoiController

    return PetoiController()


class Body:
    def __init__(self, robot: RobotController):
        self.robot = robot
        self.current: str | None = None
        self.since = time.monotonic()
        self.stop_at: float | None = None  # when the running gait must stop

    def _send(self, action: str) -> bool:
        """Send a skill; only update state if the robot actually got it."""
        if not self.robot.execute_action(f"k{action}"):
            return False
        self.current, self.since = action, time.monotonic()
        return True

    def _state(self) -> dict:
        return {
            "current_action": self.current,
            "since_s": round(time.monotonic() - self.since, 2),
            "stops_in_s": round(self.stop_at - time.monotonic(), 2) if self.stop_at else None,
        }

    def on_act(self, msg):
        action = str(msg.get("action", ""))
        if action not in PETOI_COMMANDS:
            return m.error(f"unknown action {msg.get('action')!r}")
        duration = msg.get("duration_s")
        if duration is not None and (
            isinstance(duration, bool) or not isinstance(duration, (int, float))
        ):
            return m.error(f"duration_s must be a number, got {duration!r}")
        limit = gait_limit(duration) if action in GAITS else None  # validate before moving
        if not self._send(action):
            return m.error(f"could not send {action!r} to the robot")
        self.stop_at = time.monotonic() + limit if limit else None
        return m.ok(**self._state())

    def on_raw(self, msg):
        # Deliberately does not touch current/stop_at: raw joint moves are for
        # tuning/debugging and leave any running gait and its watchdog alone.
        cmd = str(msg.get("cmd", "")).strip()
        if not raw_is_safe(cmd):
            return m.error(f"raw command not allowed: {cmd!r}")
        if not self.robot.send_raw(cmd):
            return m.error(f"could not send {cmd!r} to the robot")
        return m.ok()

    def on_stop(self, msg):
        self.stop_at = None
        if not self._send(config.STOP_ACTION):
            return m.error("could not send stop to the robot")
        return m.ok(**self._state())

    def on_state(self, msg):
        return m.ok(**self._state())

    def tick(self):
        if self.stop_at and time.monotonic() >= self.stop_at:
            logger.info("gait %s reached its time limit — stopping", self.current)
            self.stop_at = None  # clear first so a failed stop isn't retried every tick
            self._send(config.STOP_ACTION)


def main():
    setup_logging()
    robot = make_robot()
    robot.connect()
    body = Body(robot)
    logger.info("body service ready (gait limit %s s)", config.GAIT_MAX_S or "none")
    Server(
        ep.bind_addr(ep.BODY_CMD),
        {"act": body.on_act, "raw": body.on_raw, "stop": body.on_stop, "state": body.on_state},
        "body",
    ).serve_forever(tick=body.tick, tick_ms=config.TICK_MS)


if __name__ == "__main__":
    main()
