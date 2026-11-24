"""Kokoro Text-to-Speech."""

import io
import logging

import numpy as np
import scipy.signal
import soundfile as sf
from kokoro import KPipeline

logger = logging.getLogger(__name__)


def resample(waveform, target_rate: int, original_rate: int):
    if target_rate == original_rate:
        return waveform
    return scipy.signal.resample(waveform, int(waveform.shape[0] * target_rate / original_rate))


class Synthesizer:
    """Kokoro text-to-speech: text in, WAV bytes (at the playback sample rate) out."""

    def __init__(
        self,
        voice: str,
        lang_code: str,
        speed: float,
        playback_rate: int,
        model_rate: int,
    ):
        logger.info("Loading Kokoro (voice=%s)...", voice)
        self.voice = voice
        self.speed = speed
        self.model_rate = model_rate
        self.playback_rate = playback_rate
        self.pipeline = KPipeline(lang_code=lang_code)
        logger.info("Kokoro ready")

    def synthesize(self, text: str) -> bytes:
        chunks = self.pipeline(text, voice=self.voice, speed=self.speed, split_pattern=r"\n+")
        waveform = resample(
            np.concatenate([audio for _, _, audio in chunks]),
            original_rate=self.model_rate,
            target_rate=self.playback_rate,
        )
        buf = io.BytesIO()
        sf.write(buf, waveform, self.playback_rate, format="wav", subtype="PCM_16")
        return buf.getvalue()
