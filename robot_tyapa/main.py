from dotenv import load_dotenv

load_dotenv()

import logging

from robot_tyapa.audio.capture import capture_with_vad
from robot_tyapa.audio.playback import play_wav_bytes
from robot_tyapa.brain.local import LocalBrain
from robot_tyapa.config import (
    BRAIN_DEFAULT_ACTION,
    CHUNK_SIZE,
    LLM_MODEL,
    LLM_PROVIDER,
    PLAYBACK_DEVICE,
    RECORD_DEVICE,
    SAMPLE_RATE,
    STT_MODEL,
    TTS_LANG_CODE,
    TTS_SPEED,
    TTS_VOICE,
    VAD_MAX_RECORD_S,
    VAD_MIN_SPEECH_S,
    VAD_RMS_THRESHOLD,
    VAD_SILENCE_MS,
)
from robot_tyapa.robot.petoi import PetoiController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    robot = PetoiController()
    robot.connect()

    logger.info("Loading models — this takes ~30s on first run...")
    brain = LocalBrain(
        provider=LLM_PROVIDER,
        model=LLM_MODEL,
        stt_model=STT_MODEL,
        tts_voice=TTS_VOICE,
        tts_lang_code=TTS_LANG_CODE,
        tts_speed=TTS_SPEED,
    )

    current_action = BRAIN_DEFAULT_ACTION
    logger.info("Tyapa online. Listening...")

    try:
        while True:
            wav = capture_with_vad(
                device_name=RECORD_DEVICE,
                rate=SAMPLE_RATE,
                chunk_size=CHUNK_SIZE,
                rms_threshold=VAD_RMS_THRESHOLD,
                silence_ms=VAD_SILENCE_MS,
                max_seconds=VAD_MAX_RECORD_S,
                min_speech_seconds=VAD_MIN_SPEECH_S,
            )
            if wav is None:
                continue

            wav_resp, text, action = brain.process(wav, current_action)
            if text:
                logger.info("Response: %r", text)

            # Act before speaking so the dog moves while the audio plays
            if action:
                robot.execute_action(action)
                current_action = action

            if wav_resp:
                play_wav_bytes(wav_resp, device_name=PLAYBACK_DEVICE)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        robot.disconnect()


if __name__ == "__main__":
    main()
