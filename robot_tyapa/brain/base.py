from abc import ABC, abstractmethod


class BrainInterface(ABC):
    @abstractmethod
    def process(
        self, audio_bytes: bytes, current_action: str
    ) -> tuple[bytes | None, str, str | None]:
        """
        Process audio and return (wav_response_bytes, spoken_text, serial_action).
        serial_action is a complete command string e.g. "ksit", "kwkF", or None.
        """
