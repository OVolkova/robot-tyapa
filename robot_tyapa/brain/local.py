import logging

from robot_tyapa.brain.base import BrainInterface
from robot_tyapa.brain.speech_to_speech import SpeechToSpeechActionProcessor

logger = logging.getLogger(__name__)


class LocalBrain(BrainInterface):
    """Runs SpeechToSpeechActionProcessor directly on-device.
    Model loading (~30s on Pi 5) happens at construction time."""

    def __init__(
        self,
        provider: str,
        model: str,
        stt_model: str,
        tts_voice: str,
        tts_lang_code: str,
        tts_speed: float,
    ) -> None:
        self._processor = SpeechToSpeechActionProcessor(
            provider=provider,
            model=model,
            stt_model=stt_model,
            tts_voice=tts_voice,
            tts_lang_code=tts_lang_code,
            tts_speed=tts_speed,
        )
        logger.info("LocalBrain ready")

    def process(
        self, audio_bytes: bytes, current_action: str
    ) -> tuple[bytes | None, str, str | None]:
        wav_buf, text, action = self._processor.process(audio_bytes, current_action)
        wav_bytes: bytes | None = None
        if wav_buf is not None:
            raw = wav_buf.read()
            wav_bytes = raw if raw else None
        return wav_bytes, text, action
