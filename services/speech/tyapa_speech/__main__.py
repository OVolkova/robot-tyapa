"""Speech service: the only process that owns the speaker. Text -> Kokoro -> speaker."""

import logging
import time

from tyapa_protocol import endpoints as ep
from tyapa_protocol import messages as m
from tyapa_protocol import setup_logging
from tyapa_protocol.transport import Server

from . import config
from .playback import play_wav_bytes
from .tts import SpeechModels

log = logging.getLogger("tyapa.speech")


class Speech:
    def __init__(self):
        self.models = SpeechModels(
            voice=config.TTS_VOICE,
            lang_code=config.TTS_LANG_CODE,
            speed=config.TTS_SPEED,
            playback_freq=config.PLAYBACK_FREQUENCY,
        )

    def on_say(self, msg):
        text = str(msg.get("text", "")).strip()
        if not text:
            return m.ok(spoken_s=0)
        t0 = time.monotonic()
        play_wav_bytes(self.models.synthesize(text), device_name=config.PLAYBACK_DEVICE)
        return m.ok(spoken_s=round(time.monotonic() - t0, 2))


def main():
    setup_logging()
    speech = Speech()
    log.info("speech service ready")
    Server(ep.bind_addr(ep.SPEECH_CMD), {"say": speech.on_say}, "speech").serve_forever()


if __name__ == "__main__":
    main()
