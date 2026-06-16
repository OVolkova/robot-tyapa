import io
import logging
import wave

import numpy as np

from robot_tyapa.audio import _suppress_stderr
from robot_tyapa.config import (
    CHUNK_SIZE,
    RECORD_DEVICE,
    SAMPLE_RATE,
    VAD_MAX_RECORD_S,
    VAD_MIN_SPEECH_S,
    VAD_NO_SPEECH_TIMEOUT_S,
    VAD_SILENCE_MS,
    VAD_THRESHOLD,
)

logger = logging.getLogger(__name__)

_ECHO_SKIP_S = 0.3  # discard this many seconds after playback to avoid echo

_vad_model = None


def _get_vad_model():
    global _vad_model
    if _vad_model is None:
        from silero_vad import load_silero_vad

        logger.debug("Loading silero-vad model")
        _vad_model = load_silero_vad()
    return _vad_model


def _rms(chunk_bytes: bytes) -> float:
    samples = np.frombuffer(chunk_bytes, dtype=np.int32).astype(np.float64)
    return float(np.sqrt(np.mean(samples**2)))


def _encode_wav(frames: list[bytes], rate: int, channels: int, sample_width: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(b"".join(frames))
    return buf.getvalue()


def _find_input_device(pa, name: str) -> int | None:
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0 and name in info["name"]:
            return i
    # fallback: first available input device
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            logger.warning("Device %r not found; using %r", name, info["name"])
            return i
    return None


def capture_with_vad(
    device_name: str = RECORD_DEVICE,
    rate: int = SAMPLE_RATE,
    chunk_size: int = CHUNK_SIZE,
    vad_threshold: float = VAD_THRESHOLD,
    silence_ms: int = VAD_SILENCE_MS,
    max_seconds: float = VAD_MAX_RECORD_S,
    min_speech_seconds: float = VAD_MIN_SPEECH_S,
    no_speech_timeout: float = VAD_NO_SPEECH_TIMEOUT_S,
) -> bytes | None:
    """Block until speech + trailing silence detected. Returns WAV bytes or None."""
    import pyaudio
    import torch
    from silero_vad import VADIterator

    with _suppress_stderr():
        pa = pyaudio.PyAudio()
    device_index = _find_input_device(pa, device_name)

    max_chunks = int(max_seconds * rate / chunk_size)
    no_speech_chunks = int(no_speech_timeout * rate / chunk_size)
    skip_chunks = int(_ECHO_SKIP_S * rate / chunk_size)

    model = _get_vad_model()
    vad_iter = VADIterator(
        model,
        threshold=vad_threshold,
        sampling_rate=rate,
        min_silence_duration_ms=silence_ms,
    )

    stream = pa.open(
        format=pyaudio.paInt32,
        channels=1,
        rate=rate,
        input=True,
        input_device_index=device_index,
        frames_per_buffer=chunk_size,
    )

    try:
        recording = False
        frames: list[bytes] = []
        pre_speech_chunks = 0
        speech_chunks = 0

        for _ in range(skip_chunks):
            stream.read(chunk_size)

        logger.debug("VAD: listening (silero, threshold=%.2f)", vad_threshold)

        while True:
            chunk = stream.read(chunk_size)
            samples = np.frombuffer(chunk, dtype=np.int32).astype(np.float32) / (2**31)
            event = vad_iter(torch.from_numpy(samples), return_seconds=False)

            if not recording:
                pre_speech_chunks += 1
                if event and "start" in event:
                    recording = True
                    frames = [chunk]
                    speech_chunks = 1
                    logger.debug("VAD: speech start")
                elif pre_speech_chunks >= no_speech_chunks:
                    logger.debug("VAD: no speech timeout")
                    return None
            else:
                frames.append(chunk)
                speech_chunks += 1

                if event and "end" in event:
                    logger.debug("VAD: speech end (silence)")
                    break
                if speech_chunks >= max_chunks:
                    logger.debug("VAD: max duration reached")
                    break

    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()

    if not frames:
        return None

    speech_seconds = len(frames) * chunk_size / rate
    if speech_seconds < min_speech_seconds:
        logger.debug("VAD: discarding short burst (%.2fs)", speech_seconds)
        return None

    sample_width = pyaudio.get_sample_size(pyaudio.paInt32)
    return _encode_wav(frames, rate, 1, sample_width)
