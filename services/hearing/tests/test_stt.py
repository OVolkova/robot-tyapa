from unittest.mock import MagicMock, patch

import numpy as np

from tyapa_hearing.stt import SpeechModels, SpeechToText, get_device, resample

_DUMMY_WAV = b"RIFF\x00\x00\x00\x00WAVEfmt "


# -- get_device ------------------------------------------------------------


def test_get_device_returns_mps_when_cuda_unavailable():
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.backends.mps.is_available.return_value = True
    with patch("tyapa_hearing.stt.torch", mock_torch):
        assert get_device() == "mps"


# -- resample ---------------------------------------------------------------


def test_resample_same_freq_returns_unchanged():
    wf = np.ones(16000, dtype=np.float32)
    assert resample(wf, 16000, 16000) is wf


def test_resample_different_freq_calls_scipy():
    wf = np.ones(16000, dtype=np.float32)
    result = resample(wf, 8000, 16000)
    assert result.shape == (8000,)


# -- SpeechToText -----------------------------------------------------------


def test_speech_to_text_init():
    with (
        patch("tyapa_hearing.stt.WhisperProcessor"),
        patch("tyapa_hearing.stt.WhisperForConditionalGeneration"),
        patch("tyapa_hearing.stt.get_device", return_value="cpu"),
    ):
        stt = SpeechToText(model_name="openai/whisper-tiny.en")
    assert stt.model_freq == 16000


def test_speech_to_text_call():
    stt = SpeechToText.__new__(SpeechToText)
    stt.device = "cpu"
    stt.model_freq = 16000
    stt.processor = MagicMock()
    stt.model = MagicMock()
    stt.processor.batch_decode.return_value = ["hello world"]

    waveform = np.ones(16000, dtype=np.float32)
    result = stt(waveform, 16000)
    assert result == "hello world"


# -- SpeechModels.transcribe --


def test_transcribe_decodes_wav_and_calls_stt():
    models = SpeechModels.__new__(SpeechModels)
    models.stt = MagicMock(return_value="sit down please")

    mock_ta = MagicMock()
    mock_ta.load.return_value = (
        MagicMock(numpy=MagicMock(return_value=np.ones((1, 16000)))),
        16000,
    )
    with patch("tyapa_hearing.stt.torchaudio", mock_ta):
        result = models.transcribe(_DUMMY_WAV)

    assert result == "sit down please"
    models.stt.assert_called_once()
    args, _ = models.stt.call_args
    assert args[1] == 16000
