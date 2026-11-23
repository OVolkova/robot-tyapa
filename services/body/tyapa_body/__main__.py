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

log = logging.getLogger("tyapa.body")

# Raw joint moves the brain may send, e.g. "m0 40" or "m0 30 8 -20". Nothing else raw.
RAW_OK = re.compile(r"^m\d{1,2} -?\d{1,3}( \d{1,2} -?\d{1,3})*$")


def canonical(action: str) -> str | None:
    """Return action if it is a known skill key, else None."""
    return action if action in PETOI_COMMANDS else None


def is_gait(action: str) -> bool:
    return action in GAITS


def gait_limit(requested: float | None) -> float | None:
    caps = [x for x in (requested, config.GAIT_MAX_S) if x and x > 0]
    return min(caps) if caps else None


class DryRunRobot:
    def connect(self):
        log.info("DRY RUN — no serial port")

    def execute_action(self, action):
        log.info("DRY %s", action)

    def send_raw(self, cmd):
        log.info("DRY %s", cmd)


class Body:
    def __init__(self):
        if config.DRY_RUN:
            self.robot = DryRunRobot()
        else:
            from .petoi import PetoiController

            self.robot = PetoiController()
        self.robot.connect()
        self.current: str | None = None
        self.since = time.monotonic()
        self.stop_at: float | None = None  # when the running gait must stop

    def _send(self, action: str) -> None:
        self.robot.execute_action(f"k{action}")
        self.current, self.since = action, time.monotonic()

    def _state(self) -> dict:
        return {
            "current_action": self.current,
            "since_s": round(time.monotonic() - self.since, 2),
            "stops_in_s": round(self.stop_at - time.monotonic(), 2) if self.stop_at else None,
        }

    def on_act(self, msg):
        action = canonical(str(msg.get("action", "")))
        if action is None:
            return m.error(f"unknown action {msg.get('action')!r}")
        self._send(action)
        limit = gait_limit(msg.get("duration_s")) if is_gait(action) else None
        self.stop_at = time.monotonic() + limit if limit else None
        return m.ok(**self._state())

    def on_raw(self, msg):
        # Deliberately does not touch current/stop_at: raw joint moves are for
        # tuning/debugging and leave any running gait and its watchdog alone.
        cmd = str(msg.get("cmd", "")).strip()
        if not RAW_OK.match(cmd):
            return m.error(f"raw command not allowed: {cmd!r}")
        self.robot.send_raw(cmd)
        return m.ok()

    def on_stop(self, msg):
        self._send(config.STOP_ACTION)
        self.stop_at = None
        return m.ok(**self._state())

    def on_state(self, msg):
        return m.ok(**self._state())

    def tick(self):
        if self.stop_at and time.monotonic() >= self.stop_at:
            log.info("gait %s reached its time limit — stopping", self.current)
            self.stop_at = None
            self._send(config.STOP_ACTION)


def main():
    setup_logging()
    body = Body()
    log.info("body service ready (gait limit %s s)", config.GAIT_MAX_S or "none")
    Server(
        ep.bind_addr(ep.BODY_CMD),
        {"act": body.on_act, "raw": body.on_raw, "stop": body.on_stop, "state": body.on_state},
        "body",
    ).serve_forever(tick=body.tick, tick_ms=config.TICK_MS)


if __name__ == "__main__":
    main()
