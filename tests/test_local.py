import io
from unittest.mock import patch

_DEFAULT_KWARGS = dict(
    provider=None,
    model=None,
    stt_model="openai/whisper-tiny.en",
    tts_voice="af_heart",
    tts_lang_code="b",
    tts_speed=1.0,
)


def _make_brain(**kwargs):
    with patch("robot_tyapa.brain.local.SpeechToSpeechActionProcessor") as MockProc:
        from robot_tyapa.brain.local import LocalBrain

        brain = LocalBrain(**{**_DEFAULT_KWARGS, **kwargs})
        return brain, MockProc.return_value


def test_process_calls_processor_with_correct_args():
    brain, mock_proc = _make_brain()
    mock_proc.process.return_value = (io.BytesIO(b"RIFF...."), "hello", "ksit")

    _, text, action = brain.process(b"audio_bytes", "balance")

    mock_proc.process.assert_called_once_with(b"audio_bytes", "balance")
    assert text == "hello"
    assert action == "ksit"


def test_process_returns_wav_bytes_from_bytesio():
    brain, mock_proc = _make_brain()
    wav_content = b"RIFF\x00\x00\x00\x00WAVE"
    mock_proc.process.return_value = (io.BytesIO(wav_content), "hi", None)

    wav_bytes, _, _ = brain.process(b"audio", "rest")

    assert wav_bytes == wav_content


def test_process_returns_none_for_empty_bytesio():
    brain, mock_proc = _make_brain()
    mock_proc.process.return_value = (io.BytesIO(b""), "ok", None)

    wav_bytes, _, _ = brain.process(b"audio", "balance")

    assert wav_bytes is None


def test_process_forwards_action_unchanged():
    brain, mock_proc = _make_brain()
    mock_proc.process.return_value = (io.BytesIO(b"data"), "", "kwkF")

    _, _, action = brain.process(b"audio", "balance")

    assert action == "kwkF"


def test_constructor_passes_config_to_processor():
    with patch("robot_tyapa.brain.local.SpeechToSpeechActionProcessor") as MockProc:
        from robot_tyapa.brain.local import LocalBrain

        LocalBrain(
            provider="anthropic",
            model="claude-opus-4-8",
            stt_model="openai/whisper-base.en",
            tts_voice="af_sky",
            tts_lang_code="a",
            tts_speed=1.2,
        )

        MockProc.assert_called_once_with(
            provider="anthropic",
            model="claude-opus-4-8",
            stt_model="openai/whisper-base.en",
            tts_voice="af_sky",
            tts_lang_code="a",
            tts_speed=1.2,
        )
