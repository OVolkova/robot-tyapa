from abc import ABC, abstractmethod


class RobotController(ABC):
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def execute_action(self, action: str) -> bool:
        """action is a complete serial command, e.g. 'ksit', 'kwkF'. True if it was sent."""

    @abstractmethod
    def send_raw(self, cmd: str) -> bool:
        """Send a raw token to the serial port, e.g. 'm0 40'. No whitelist. True if it was sent."""
