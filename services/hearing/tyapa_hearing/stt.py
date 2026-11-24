"""Whisper Speech-to-Text."""

import io
import logging

import scipy.signal
import torch
import torchaudio
from transformers import WhisperForConditionalGeneration, WhisperProcessor

logger = logging.getLogger(__name__)


def get_device() -> str:
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
    logger.info("device is %s", device)
    return device


def resample(waveform, target_rate: int, original_rate: int):
    if target_rate == original_rate:
        return waveform
    return scipy.signal.resample(waveform, int(waveform.shape[0] * target_rate / original_rate))


class Transcriber:
    """Whisper speech-to-text: WAV bytes in, transcript out."""

    def __init__(
        self,
        model_name: str,
        model_rate: int,
        device: str | None = None,
    ):
        logger.info("Loading Whisper %s...", model_name)
        self.device = device or get_device()
        self.processor = WhisperProcessor.from_pretrained(model_name)
        self.model = WhisperForConditionalGeneration.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.config.forced_decoder_ids = None
        self.model.generation_config.forced_decoder_ids = None
        self.model_rate = model_rate
        logger.info("Whisper ready")

    def transcribe(self, wav: bytes) -> str:
        signal, rate = torchaudio.load(io.BytesIO(wav))
        waveform = resample(signal.numpy()[0], self.model_rate, rate)
        processed = self.processor(
            waveform, sampling_rate=self.model_rate, return_tensors="pt", return_attention_mask=True
        )
        input_features = processed.input_features.to(self.device)
        attention_mask = processed.attention_mask.to(self.device)

        predicted_ids = self.model.generate(input_features, attention_mask=attention_mask)
        return self.processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
