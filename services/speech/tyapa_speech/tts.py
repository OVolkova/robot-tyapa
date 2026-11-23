"""Kokoro TTS."""

import io
import logging

import numpy as np
import scipy.signal
import soundfile as sf
from kokoro import KPipeline

logger = logging.getLogger(__name__)

KOKORO_VOICE_FREQ = 24000  # Kokoro native sample rate


def resample(waveform, target_freq: int, original_freq: int):
    if target_freq == original_freq:
        return waveform
    return scipy.signal.resample(waveform, int(waveform.shape[0] * target_freq / original_freq))


class TextToSpeech:
    def __init__(
        self,
        voice: str = "af_heart",
        lang_code: str = "b",
        speed: float = 1.0,
        model_freq: int = KOKORO_VOICE_FREQ,
        playback_freq: int = 16000,
    ):
        self.voice = voice
        self.speed = speed
        self.model_freq = model_freq
        self.playback_freq = playback_freq
        self.pipeline = KPipeline(lang_code=lang_code)

    def generate(self, text):
        generator = self.pipeline(
            text,
            voice=self.voice,
            speed=self.speed,
            split_pattern=r"\n+",
        )

        original_waveform = np.concatenate([a for _, _, a in generator])
        waveform = resample(
            original_waveform,
            original_freq=self.model_freq,
            target_freq=self.playback_freq,
        )
        return waveform, self.playback_freq


class SpeechModels:
    """The speech service's model wrapper: text in, WAV bytes out."""

    def __init__(self, voice: str, lang_code: str, speed: float, playback_freq: int):
        logger.info("Loading TextToSpeech (Kokoro voice=%s)...", voice)
        self.tts = TextToSpeech(
            voice=voice, lang_code=lang_code, speed=speed, playback_freq=playback_freq
        )
        logger.info("TextToSpeech ready")

    def synthesize(self, text: str) -> bytes:
        waveform, freq = self.tts.generate(text)
        buf = io.BytesIO()
        sf.write(buf, waveform, freq, format="wav", subtype="PCM_16")
        return buf.getvalue()
