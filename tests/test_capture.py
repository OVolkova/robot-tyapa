import struct
import sys
import wave
from unittest.mock import MagicMock, patch

import numpy as np

from robot_tyapa.audio.capture import _encode_wav, _find_input_device, _rms, capture_with_vad


def _int32_bytes(values: list[int]) -> bytes:
    return struct.pack(f"{len(values)}i", *values)


def test_rms_of_silence_is_zero():
    data = _int32_bytes([0] * 1024)
    assert _rms(data) == 0.0


def test_rms_of_constant_signal():
    value = 1_000_000
    data = _int32_bytes([value] * 1024)
    assert abs(_rms(data) - value) < 1.0


def test_rms_no_overflow_for_large_samples():
    # int32 max squared overflows int32 — must use float64 internally
    max_val = 2**31 - 1
    data = _int32_bytes([max_val] * 512 + [-max_val] * 512)
    result = _rms(data)
    assert np.isfinite(result)
    assert result > 0


def test_rms_mixed_positive_negative():
    # RMS should be same for [v, -v] as for [v, v] — sign doesn't matter
    v = 500_000
    data_pos = _int32_bytes([v] * 256 + [-v] * 256)
    data_neg = _int32_bytes([v] * 512)
    assert abs(_rms(data_pos) - _rms(data_neg)) < 1.0


def test_encode_wav_produces_valid_header():
    frames = [_int32_bytes([0] * 1024)]
    wav_bytes = _encode_wav(frames, rate=16000, channels=1, sample_width=4)
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"


def test_encode_wav_correct_parameters():
    frames = [_int32_bytes([0] * 1024)]
    wav_bytes = _encode_wav(frames, rate=16000, channels=1, sample_width=4)

    import io

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getframerate() == 16000
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 4


def test_encode_wav_contains_frame_data():
    chunk = _int32_bytes(list(range(256)))
    wav_bytes = _encode_wav([chunk], rate=16000, channels=1, sample_width=4)
    assert len(wav_bytes) > len(chunk)  # header + data


# ─── _find_input_device ──────────────────────────────────────────────────────


def _pa_mock(infos: list[dict]):
    pa = MagicMock()
    pa.get_device_count.return_value = len(infos)
    pa.get_device_info_by_index.side_effect = infos + infos  # covers both for-loops
    return pa


def test_find_input_device_finds_named_device():
    pa = _pa_mock(
        [
            {"name": "other_device", "maxInputChannels": 1},
            {"name": "mic_mono_card", "maxInputChannels": 1},
        ]
    )
    assert _find_input_device(pa, "mic_mono") == 1


def test_find_input_device_fallback_to_first_input(caplog):
    pa = _pa_mock([{"name": "builtin_mic", "maxInputChannels": 1}])
    result = _find_input_device(pa, "mic_mono")
    assert result == 0
    assert "not found" in caplog.text


def test_find_input_device_returns_none_when_no_inputs():
    pa = _pa_mock([{"name": "hdmi_output", "maxInputChannels": 0}])
    assert _find_input_device(pa, "mic_mono") is None


# ─── capture_with_vad ────────────────────────────────────────────────────────

_LOUD = np.full(1024, 10_000_000, dtype=np.int32).tobytes()  # RMS >> VAD threshold
_SILENT = np.zeros(1024, dtype=np.int32).tobytes()  # RMS = 0

# silence_ms=64 → silence_chunks_needed=1; max_seconds=0.32 → max_chunks=5
_VAD_KWARGS = dict(
    rate=16000,
    chunk_size=1024,
    rms_threshold=500,
    silence_ms=64,
    max_seconds=0.32,
    min_speech_seconds=0.1,
)


def _mock_pyaudio(chunks: list[bytes]):
    mock_stream = MagicMock()
    mock_stream.read.side_effect = list(chunks)
    mock_pa = MagicMock()
    mock_pa.open.return_value = mock_stream
    mock_pa.get_device_count.return_value = 1
    mock_pa.get_device_info_by_index.return_value = {
        "name": "test_device",
        "maxInputChannels": 1,
    }
    mock_mod = MagicMock()
    mock_mod.PyAudio.return_value = mock_pa
    mock_mod.get_sample_size.return_value = 4
    return mock_mod


def test_capture_speech_then_silence_returns_wav():
    # 4 loud chunks trigger + sustain recording; 1 silent chunk ends it
    chunks = [_LOUD] * 4 + [_SILENT]
    with (
        patch.dict(sys.modules, {"pyaudio": _mock_pyaudio(chunks)}),
        patch("robot_tyapa.audio.capture._ECHO_SKIP_S", 0),
    ):
        result = capture_with_vad(**_VAD_KWARGS)
    assert result is not None
    assert result[:4] == b"RIFF"


def test_capture_short_burst_returns_none():
    # 1 loud + 1 silent is only 0.128 s < min_speech_seconds=0.2
    chunks = [_LOUD, _SILENT]
    with (
        patch.dict(sys.modules, {"pyaudio": _mock_pyaudio(chunks)}),
        patch("robot_tyapa.audio.capture._ECHO_SKIP_S", 0),
    ):
        result = capture_with_vad(**{**_VAD_KWARGS, "min_speech_seconds": 0.2})
    assert result is None


def test_capture_max_duration_returns_wav():
    # 6 loud chunks exceed max_chunks=5; recording is cut off at max duration
    chunks = [_LOUD] * 6
    with (
        patch.dict(sys.modules, {"pyaudio": _mock_pyaudio(chunks)}),
        patch("robot_tyapa.audio.capture._ECHO_SKIP_S", 0),
    ):
        result = capture_with_vad(**_VAD_KWARGS)
    assert result is not None
    assert result[:4] == b"RIFF"
