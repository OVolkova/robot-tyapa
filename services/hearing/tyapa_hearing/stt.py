"""Whisper STT."""

import io
import logging

import scipy.signal
import torch
import torchaudio
from transformers import WhisperForConditionalGeneration, WhisperProcessor

logger = logging.getLogger(__name__)

WHISPER_FREQUENCY = 16000


def get_device() -> str:
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
    logger.info("device is %s", device)
    return device


def resample(waveform, target_freq: int, original_freq: int):
    if target_freq == original_freq:
        return waveform
    return scipy.signal.resample(waveform, int(waveform.shape[0] * target_freq / original_freq))


class SpeechToText:
    def __init__(
        self,
        model_name: str = "openai/whisper-tiny.en",
        model_freq: int = WHISPER_FREQUENCY,
        device: str | None = None,
    ):
        self.device = device or get_device()
        self.processor = WhisperProcessor.from_pretrained(model_name)
        self.model = WhisperForConditionalGeneration.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.config.forced_decoder_ids = None
        self.model.generation_config.forced_decoder_ids = None
        self.model_freq = model_freq

    def __call__(self, waveform, freq):
        waveform = resample(waveform, self.model_freq, freq)
        processed = self.processor(
            waveform, sampling_rate=self.model_freq, return_tensors="pt", return_attention_mask=True
        )
        input_features = processed.input_features.to(self.device)
        attention_mask = processed.attention_mask.to(self.device)

        predicted_ids = self.model.generate(input_features, attention_mask=attention_mask)
        transcription = self.processor.batch_decode(predicted_ids, skip_special_tokens=True)
        return transcription[0]


class SpeechModels:
    """The hearing service's model wrapper: WAV bytes in, transcript out."""

    def __init__(self, stt_model: str):
        logger.info("Loading SpeechToText (Whisper %s)...", stt_model)
        self.stt = SpeechToText(model_name=stt_model)
        logger.info("SpeechToText ready")

    def transcribe(self, wav: bytes) -> str:
        # torchaudio.load handles the WAV header.
        signal, frequency = torchaudio.load(io.BytesIO(wav))
        waveform = signal.numpy()[0]
        return self.stt(waveform, frequency)
