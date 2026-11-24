from unittest.mock import MagicMock, patch

import numpy as np

from tyapa_hearing.stt import Transcriber, get_device, resample

_DUMMY_WAV = b"RIFF\x00\x00\x00\x00WAVEfmt "


# -- get_device ------------------------------------------------------------


def test_get_device_returns_mps_when_cuda_unavailable():
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.backends.mps.is_available.return_value = True
    with patch("tyapa_hearing.stt.torch", mock_torch):
        assert get_device() == "mps"


# -- resample ---------------------------------------------------------------


def test_resample_same_rate_returns_unchanged():
    wf = np.ones(16000, dtype=np.float32)
    assert resample(wf, 16000, 16000) is wf


def test_resample_different_rate_calls_scipy():
    wf = np.ones(16000, dtype=np.float32)
    result = resample(wf, 8000, 16000)
    assert result.shape == (8000,)


# -- Transcriber -------------------------------------------------------------


def _transcriber() -> Transcriber:
    stt = Transcriber.__new__(Transcriber)
    stt.device = "cpu"
    stt.model_rate = 16000
    stt.processor = MagicMock()
    stt.model = MagicMock()
    stt.processor.batch_decode.return_value = ["hello world"]
    return stt


def _fake_torchaudio(rate: int = 16000) -> MagicMock:
    mock_ta = MagicMock()
    mock_ta.load.return_value = (
        MagicMock(numpy=MagicMock(return_value=np.ones((1, rate)))),
        rate,
    )
    return mock_ta


def test_transcriber_init():
    with (
        patch("tyapa_hearing.stt.WhisperProcessor") as processor,
        patch("tyapa_hearing.stt.WhisperForConditionalGeneration") as model,
        patch("tyapa_hearing.stt.get_device", return_value="cpu"),
    ):
        stt = Transcriber(model_name="openai/whisper-tiny.en", model_rate=16000)
    assert stt.model_rate == 16000
    assert stt.device == "cpu"
    processor.from_pretrained.assert_called_once_with("openai/whisper-tiny.en")
    model.from_pretrained.assert_called_once_with("openai/whisper-tiny.en")


def test_transcribe_decodes_wav_and_returns_text():
    stt = _transcriber()
    with patch("tyapa_hearing.stt.torchaudio", _fake_torchaudio()):
        assert stt.transcribe(_DUMMY_WAV) == "hello world"


def test_transcribe_resamples_to_whisper_rate():
    stt = _transcriber()
    with patch("tyapa_hearing.stt.torchaudio", _fake_torchaudio(rate=48000)):
        stt.transcribe(_DUMMY_WAV)
    waveform = stt.processor.call_args.args[0]
    assert waveform.shape == (16000,)  # 48 kHz input brought down to the model rate
    assert stt.processor.call_args.kwargs["sampling_rate"] == 16000
