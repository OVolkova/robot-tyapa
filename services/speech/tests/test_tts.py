from unittest.mock import MagicMock, patch

import numpy as np

from tyapa_speech.tts import Synthesizer, TextToSpeech, resample

# -- resample ---------------------------------------------------------------


def test_resample_same_freq_returns_unchanged():
    wf = np.ones(16000, dtype=np.float32)
    assert resample(wf, 16000, 16000) is wf


def test_resample_different_freq_calls_scipy():
    wf = np.ones(16000, dtype=np.float32)
    result = resample(wf, 8000, 16000)
    assert result.shape == (8000,)


# -- TextToSpeech -------------------------------------------------------------


def test_text_to_speech_init():
    mock_pipeline_cls = MagicMock()
    with patch("tyapa_speech.tts.KPipeline", mock_pipeline_cls):
        tts = TextToSpeech(voice="af_sky", lang_code="a", speed=1.2, playback_freq=16000)
    assert tts.voice == "af_sky"
    assert tts.speed == 1.2
    mock_pipeline_cls.assert_called_once_with(lang_code="a")


def test_text_to_speech_generate():
    mock_waveform = np.ones(24000, dtype=np.float32)
    mock_pipeline_instance = MagicMock()
    mock_pipeline_instance.return_value = [("gs", "ps", mock_waveform)]
    mock_signal = MagicMock()
    mock_signal.resample.return_value = np.ones(16000, dtype=np.float32)
    with (
        patch("tyapa_speech.tts.KPipeline", return_value=mock_pipeline_instance),
        patch("tyapa_speech.tts.scipy.signal", mock_signal),
    ):
        tts = TextToSpeech(voice="af_heart", lang_code="b", speed=1.0, playback_freq=16000)
        _, freq = tts.generate("hello")
    assert freq == 16000


def test_generate_concatenates_all_chunks():
    chunks = [("g", "p", np.ones(24000, dtype=np.float32)) for _ in range(2)]
    with patch("tyapa_speech.tts.KPipeline", return_value=MagicMock(return_value=chunks)):
        tts = TextToSpeech(voice="af_heart", lang_code="b", speed=1.0, playback_freq=24000)
        waveform, _ = tts.generate("one.\ntwo.")
    assert waveform.shape[0] == 48000


# -- Synthesizer.synthesize --


def test_synthesize_encodes_wav_bytes():
    models = Synthesizer.__new__(Synthesizer)
    models.tts = MagicMock()
    models.tts.generate.return_value = (np.ones(16000, dtype=np.float32), 16000)

    result = models.synthesize("Good boy!")

    models.tts.generate.assert_called_once_with("Good boy!")
    assert isinstance(result, bytes)
    assert result[:4] == b"RIFF"
