import io
import logging
import wave

import numpy as np

# from robot_tyapa.audio import _suppress_stderr
from robot_tyapa.config import (
    CHUNK_SIZE,
    RECORD_DEVICE,
    SAMPLE_RATE,
    VAD_MAX_RECORD_S,
    VAD_MIN_SPEECH_S,
    VAD_RMS_THRESHOLD,
    VAD_SILENCE_MS,
)

logger = logging.getLogger(__name__)

_ECHO_SKIP_S = 0.3  # discard this many seconds after playback to avoid echo


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
    rms_threshold: int = VAD_RMS_THRESHOLD,
    silence_ms: int = VAD_SILENCE_MS,
    max_seconds: float = VAD_MAX_RECORD_S,
    min_speech_seconds: float = VAD_MIN_SPEECH_S,
) -> bytes | None:
    """Block until speech + trailing silence detected. Returns WAV bytes or None."""
    import pyaudio

    # with _suppress_stderr():
    pa = pyaudio.PyAudio()
    device_index = _find_input_device(pa, device_name)

    silence_chunks_needed = int((silence_ms / 1000) * rate / chunk_size)
    max_chunks = int(max_seconds * rate / chunk_size)
    skip_chunks = int(_ECHO_SKIP_S * rate / chunk_size)

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
        silence_count = 0
        total_chunks = 0

        # burn a few chunks to avoid capturing speaker echo
        for _ in range(skip_chunks):
            stream.read(chunk_size)

        logger.debug("VAD: listening (threshold=%d)", rms_threshold)

        while True:
            chunk = stream.read(chunk_size)
            energy = _rms(chunk)

            if not recording:
                if energy > rms_threshold:
                    recording = True
                    silence_count = 0
                    frames = [chunk]
                    logger.debug("VAD: speech start (rms=%.0f)", energy)
            else:
                frames.append(chunk)
                total_chunks += 1

                if energy <= rms_threshold:
                    silence_count += 1
                else:
                    silence_count = 0

                if silence_count >= silence_chunks_needed:
                    logger.debug("VAD: speech end (silence)")
                    break
                if total_chunks >= max_chunks:
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
