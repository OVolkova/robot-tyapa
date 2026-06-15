import io as _io
from unittest.mock import MagicMock, patch

import numpy as np

from robot_tyapa.brain.speech_to_speech import (
    _KEEP_RECENT,
    _MAX_HISTORY,
    SpeechToSpeechActionProcessor,
    SpeechToText,
    TextToSpeech,
    TextToText,
    get_device,
    resample,
)

_DUMMY_WAV = b"RIFF\x00\x00\x00\x00WAVEfmt "


def _make_processor(
    llm_text: str = "Hello!", llm_action: str | None = None
) -> SpeechToSpeechActionProcessor:
    proc = SpeechToSpeechActionProcessor.__new__(SpeechToSpeechActionProcessor)
    proc.speech_to_text = MagicMock(return_value="sit down please")
    proc.text_to_speech = MagicMock()
    proc.text_to_speech.generate.return_value = (MagicMock(), 16000)
    proc.text_to_text = MagicMock()
    proc.text_to_text.generate.return_value = (llm_text, llm_action)
    return proc


def _run(proc: SpeechToSpeechActionProcessor, current_action: str = "balance"):
    mock_ta = MagicMock()
    mock_ta.load.return_value = (MagicMock(), 16000)
    mock_sf = MagicMock()
    mock_sf.write.side_effect = lambda buf, *a, **kw: buf.write(b"WAVDATA")
    with (
        patch("robot_tyapa.brain.speech_to_speech.torchaudio", mock_ta),
        patch("robot_tyapa.brain.speech_to_speech.sf", mock_sf),
    ):
        return proc.process(_DUMMY_WAV, current_action=current_action)


def _make_text_to_text(llm_text: str = "Hello!", llm_action: str | None = None) -> TextToText:
    tt = TextToText.__new__(TextToText)
    tt.llm = MagicMock()
    tt.llm.complete.return_value = (llm_text, llm_action)
    tt.history = []
    return tt


# ── SpeechToSpeechActionProcessor.process() return shape ─────────────────────


def test_process_returns_three_tuple():
    result = _run(_make_processor())
    assert len(result) == 3


def test_process_audio_is_bytesio():
    out_buf, _, _ = _run(_make_processor())
    assert isinstance(out_buf, _io.BytesIO)
    assert len(out_buf.read()) > 0


def test_process_response_text():
    _, text, _ = _run(_make_processor(llm_text="Woof!"))
    assert text == "Woof!"


def test_process_action_returned():
    _, _, action = _run(_make_processor(llm_action="sit"))
    assert action == "ksit"


def test_process_no_action_is_none():
    _, _, action = _run(_make_processor(llm_action=None))
    assert action is None


# ── current_action forwarded ──────────────────────────────────────────────────


def test_current_action_forwarded_to_text_to_text():
    proc = _make_processor()
    _run(proc, current_action="trF")
    _, call_action = proc.text_to_text.generate.call_args[0]
    assert call_action == "trF"


# ── fallback spoken text ──────────────────────────────────────────────────────


def test_no_tts_when_llm_returns_empty():
    proc = _make_processor(llm_text="")
    _run(proc)
    proc.text_to_speech.generate.assert_not_called()


def test_no_tts_when_llm_returns_whitespace_only():
    proc = _make_processor(llm_text="   ")
    _run(proc)
    proc.text_to_speech.generate.assert_not_called()


def test_no_fallback_when_llm_has_text():
    proc = _make_processor(llm_text="Good boy!")
    _run(proc)
    proc.text_to_speech.generate.assert_called_once_with("Good boy!")


# ── TextToText: conversation history ─────────────────────────────────────────


def test_history_empty_before_first_call():
    tt = _make_text_to_text()
    assert len(tt.history) == 0


def test_history_has_two_entries_after_one_call():
    tt = _make_text_to_text()
    tt.generate("hello", "balance")
    assert len(tt.history) == 2


def test_history_roles_alternate():
    tt = _make_text_to_text()
    tt.generate("hello", "balance")
    roles = [m["role"] for m in tt.history]
    assert roles == ["user", "assistant"]


def test_history_summarised_when_full():
    tt = _make_text_to_text()
    for _ in range(5):
        tt.generate("hello", "balance")
    assert len(tt.history) == _KEEP_RECENT + 1


def test_summary_message_is_system_role():
    tt = _make_text_to_text()
    for _ in range(5):
        tt.generate("hello", "balance")
    assert tt.history[0]["role"] == "system"
    assert "Summary" in tt.history[0]["content"]


def test_summary_calls_llm_with_old_messages():
    tt = _make_text_to_text()
    for _ in range(5):
        tt.generate("hello", "balance")
    _, last_call_kwargs = tt.llm.complete.call_args
    assert "tools" not in last_call_kwargs


def test_history_stays_bounded_across_multiple_summarisations():
    tt = _make_text_to_text()
    for _ in range(12):
        tt.generate("hello", "balance")
    assert len(tt.history) < _MAX_HISTORY


def test_history_fed_into_subsequent_call():
    tt = _make_text_to_text()
    tt.generate("hello", "balance")
    tt.generate("world", "sit")
    messages = tt.llm.complete.call_args[0][0]
    # system + 2 history entries + new user = 4
    assert len(messages) == 4


# ── TextToText: LLM message construction ─────────────────────────────────────


def test_current_action_appears_in_user_message():
    tt = _make_text_to_text()
    tt.generate("hello", "trF")
    messages = tt.llm.complete.call_args[0][0]
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "trF" in user_msg["content"]


def test_system_message_is_first():
    tt = _make_text_to_text()
    tt.generate("hello", "balance")
    messages = tt.llm.complete.call_args[0][0]
    assert messages[0]["role"] == "system"


# ── get_device ────────────────────────────────────────────────────────────────


def test_get_device_returns_mps_when_cuda_unavailable():
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.backends.mps.is_available.return_value = True
    with patch("robot_tyapa.brain.speech_to_speech.torch", mock_torch):
        assert get_device() == "mps"


# ── resample ──────────────────────────────────────────────────────────────────


def test_resample_same_freq_returns_unchanged():
    wf = np.ones(16000, dtype=np.float32)
    assert resample(wf, 16000, 16000) is wf


def test_resample_different_freq_calls_scipy():
    wf = np.ones(16000, dtype=np.float32)
    result = resample(wf, 8000, 16000)
    assert result.shape == (8000,)


# ── TextToText.__init__ ───────────────────────────────────────────────────────


def test_text_to_text_init():
    with patch("robot_tyapa.brain.speech_to_speech.create_llm_client") as mock_create:
        tt = TextToText(provider="openai", model="gpt-5.4-nano")
    mock_create.assert_called_once_with(provider="openai", model="gpt-5.4-nano")
    assert tt.history == []


# ── TextToSpeech ──────────────────────────────────────────────────────────────


def test_text_to_speech_init():
    mock_pipeline_cls = MagicMock()
    with patch("robot_tyapa.brain.speech_to_speech.KPipeline", mock_pipeline_cls):
        tts = TextToSpeech(voice="af_sky", lang_code="a", speed=1.2)
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
        patch("robot_tyapa.brain.speech_to_speech.KPipeline", return_value=mock_pipeline_instance),
        patch("robot_tyapa.brain.speech_to_speech.scipy.signal", mock_signal),
    ):
        tts = TextToSpeech(voice="af_heart", lang_code="b")
        _, freq = tts.generate("hello")
    assert freq == 16000  # ESP32_FREQUENCY


# ── SpeechToText ──────────────────────────────────────────────────────────────


def test_speech_to_text_init():
    with (
        patch("robot_tyapa.brain.speech_to_speech.WhisperProcessor"),
        patch("robot_tyapa.brain.speech_to_speech.WhisperForConditionalGeneration"),
        patch("robot_tyapa.brain.speech_to_speech.get_device", return_value="cpu"),
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


# ── SpeechToSpeechActionProcessor.__init__ ────────────────────────────────────


def test_speech_to_speech_processor_init():
    with (
        patch("robot_tyapa.brain.speech_to_speech.SpeechToText") as MockSTT,
        patch("robot_tyapa.brain.speech_to_speech.TextToSpeech") as MockTTS,
        patch("robot_tyapa.brain.speech_to_speech.TextToText") as MockTTT,
    ):
        SpeechToSpeechActionProcessor(
            provider="openai",
            model="gpt-5.4-nano",
            stt_model="openai/whisper-tiny.en",
            tts_voice="af_heart",
            tts_lang_code="b",
            tts_speed=1.0,
        )
    MockSTT.assert_called_once_with(model_name="openai/whisper-tiny.en")
    MockTTS.assert_called_once_with(voice="af_heart", lang_code="b", speed=1.0)
    MockTTT.assert_called_once_with(provider="openai", model="gpt-5.4-nano")
