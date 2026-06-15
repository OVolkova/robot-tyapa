import io
import os
import wave

import pytest

from robot_tyapa.brain.speech_to_speech import SpeechToSpeechActionProcessor, TextToSpeech
from robot_tyapa.robot.petoi_commands import PETOI_COMMANDS

pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — integration tests skipped",
)


@pytest.fixture(scope="module")
def processor():
    return SpeechToSpeechActionProcessor(
        provider="openai",
        model="gpt-5.4-nano",
        stt_model="openai/whisper-tiny.en",
        tts_voice="af_heart",
        tts_lang_code="b",
        tts_speed=1.0,
    )


@pytest.fixture(scope="module")
def input_wav():
    """Generate real WAV audio via Kokoro TTS — no fixture file needed."""
    import soundfile as sf

    tts = TextToSpeech()
    waveform, freq = tts.generate("sit down please")
    buf = io.BytesIO()
    sf.write(buf, waveform, freq, format="wav", subtype="PCM_16")
    return buf.getvalue()


def test_pipeline_runs_without_error(processor, input_wav):
    buf, text, action = processor.process(input_wav, current_action="balance")
    assert isinstance(buf, io.BytesIO)
    assert isinstance(text, str)
    assert action is None or isinstance(action, str)


def test_pipeline_produces_action_or_text(processor, input_wav):
    # LLM must respond with at least one: spoken text or a robot action
    _, text, action = processor.process(input_wav, current_action="balance")
    assert text.strip() or action is not None


def test_pipeline_wav_valid_when_text_returned(processor, input_wav):
    # When the LLM returns spoken text, the output must be a valid WAV
    # When it returns action-only (no text), an empty buffer is correct by design
    buf, text, _ = processor.process(input_wav, current_action="balance")
    if text.strip():
        data = buf.read()
        assert data[:4] == b"RIFF"
        with wave.open(io.BytesIO(data)) as wf:
            assert wf.getnframes() > 0
    else:
        assert buf.read() == b""


def test_pipeline_action_is_valid_petoi_command(processor, input_wav):
    _, _, action = processor.process(input_wav, current_action="balance")
    if action is not None:
        assert action.startswith("k"), f"action {action!r} missing 'k' prefix"
        assert action[1:] in PETOI_COMMANDS, f"unknown command: {action!r}"
