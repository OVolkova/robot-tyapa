import io
import wave
from unittest.mock import MagicMock, patch

import numpy as np

from tyapa_speech.tts import Synthesizer, resample

# -- resample ---------------------------------------------------------------


def test_resample_same_rate_returns_unchanged():
    wf = np.ones(16000, dtype=np.float32)
    assert resample(wf, 16000, 16000) is wf


def test_resample_different_rate_calls_scipy():
    wf = np.ones(16000, dtype=np.float32)
    result = resample(wf, 8000, 16000)
    assert result.shape == (8000,)


# -- Synthesizer -------------------------------------------------------------


def _synthesizer(chunks, playback_rate: int = 16000) -> Synthesizer:
    pipeline = MagicMock(return_value=chunks)
    with patch("tyapa_speech.tts.KPipeline", return_value=pipeline):
        return Synthesizer(
            voice="af_heart",
            lang_code="b",
            speed=1.0,
            playback_rate=playback_rate,
            model_rate=24000,
        )


def test_synthesizer_init():
    mock_pipeline_cls = MagicMock()
    with patch("tyapa_speech.tts.KPipeline", mock_pipeline_cls):
        tts = Synthesizer(
            voice="af_sky", lang_code="a", speed=1.2, playback_rate=16000, model_rate=24000
        )
    assert tts.voice == "af_sky"
    assert tts.speed == 1.2
    mock_pipeline_cls.assert_called_once_with(lang_code="a")


def test_synthesize_passes_voice_and_speed_to_kokoro():
    tts = _synthesizer([("g", "p", np.ones(24000, dtype=np.float32))])
    tts.synthesize("Good boy!")
    tts.pipeline.assert_called_once_with(
        "Good boy!", voice="af_heart", speed=1.0, split_pattern=r"\n+"
    )


def test_synthesize_returns_wav_at_playback_rate():
    tts = _synthesizer([("g", "p", np.ones(24000, dtype=np.float32))], playback_rate=16000)
    wav = tts.synthesize("hello")
    assert wav[:4] == b"RIFF"
    with wave.open(io.BytesIO(wav)) as wf:
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 16000  # 1 s of 24 kHz audio resampled to 16 kHz


def test_synthesize_concatenates_all_chunks():
    chunks = [("g", "p", np.ones(24000, dtype=np.float32)) for _ in range(2)]
    tts = _synthesizer(chunks, playback_rate=24000)
    with wave.open(io.BytesIO(tts.synthesize("one.\ntwo."))) as wf:
        assert wf.getnframes() == 48000
