from abc import ABC, abstractmethod


class RobotController(ABC):
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def execute_action(self, action: str) -> None:
        """action is a complete serial command, e.g. 'ksit', 'kwkF'."""

    @abstractmethod
    def get_state(self) -> str:
        """Return raw state string from robot, or empty string on timeout."""

    @abstractmethod
    def disconnect(self) -> None: ...
