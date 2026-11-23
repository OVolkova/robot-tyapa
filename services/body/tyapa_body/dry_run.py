import logging

from .base import RobotController

logger = logging.getLogger(__name__)


class DryRunRobot(RobotController):
    """Stands in for the robot on a laptop: logs commands instead of writing to a serial port."""

    def connect(self) -> None:
        logger.info("DRY RUN — no serial port")

    def execute_action(self, action: str) -> bool:
        logger.info("DRY %s", action)
        return True

    def send_raw(self, cmd: str) -> bool:
        logger.info("DRY %s", cmd)
        return True
