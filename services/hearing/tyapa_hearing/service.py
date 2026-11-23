"""Hearing service: the only process that owns the mic. Mic -> VAD -> Whisper -> event."""

import itertools
import logging
import threading
import time

from tyapa_protocol import endpoints as ep
from tyapa_protocol import messages as m
from tyapa_protocol import setup_logging
from tyapa_protocol.transport import Publisher, Server

from . import config
from .capture import capture_with_vad
from .stt import Transcriber

logger = logging.getLogger(__name__)


class Hearing:
    def __init__(self):
        self.models = Transcriber(config.STT_MODEL)
        self.listening = threading.Event()  # set = mic open
        self.last_cmd = time.monotonic()  # last time the brain told us anything
        self.utt_ids = itertools.count(1)

    # -- capture thread: owns the mic and the events socket --
    def capture_loop(self) -> None:
        events = Publisher(ep.bind_addr(ep.HEARING_EVENTS))
        while True:
            try:
                self._capture_once(events)
            except Exception:
                # never let this thread die: the service would still answer ping but be deaf
                logger.exception("capture failed -- retrying in 2s")
                time.sleep(2)
                self.listening.set()

    def _capture_once(self, events) -> None:
        if not self.listening.wait(timeout=1.0):
            if time.monotonic() - self.last_cmd > config.TURN_TIMEOUT_S:
                logger.warning("brain silent for %ss -- listening again", config.TURN_TIMEOUT_S)
                self.listening.set()
            return
        wav = capture_with_vad()
        if wav is None or not self.listening.is_set():
            return  # timeout, or we started speaking meanwhile
        t_end = time.monotonic() - config.VAD_SILENCE_MS / 1000  # when you actually stopped talking
        self.listening.clear()  # half-duplex: mic closed until the brain finishes the turn
        self.last_cmd = time.monotonic()
        utt = next(self.utt_ids)
        events.publish("hearing", m.make("speech_ended", utt=utt, t_end=t_end))
        t0 = time.monotonic()
        text = self.models.transcribe(wav).strip()
        stt_s = time.monotonic() - t0
        if not text:
            logger.info("utt %d: empty transcript, ignored", utt)
            self.listening.set()
            return
        logger.info("utt %d: heard %r (stt %.2fs)", utt, text, stt_s)
        events.publish(
            "hearing", m.make("heard", utt=utt, text=text, t_end=t_end, stt_s=round(stt_s, 3))
        )

    # -- commands from the brain (main thread) --
    def on_listen(self, msg):
        self.last_cmd = time.monotonic()
        self.listening.set()
        return m.ok()

    def on_hold(self, msg):
        """Keep the mic closed (long behaviours) and reset the turn timeout."""
        self.last_cmd = time.monotonic()
        self.listening.clear()
        return m.ok()


def main():
    setup_logging()
    hearing = Hearing()
    threading.Thread(target=hearing.capture_loop, daemon=True, name="capture").start()
    hearing.listening.set()
    logger.info("hearing service ready")
    Server(
        ep.bind_addr(ep.HEARING_CMD),
        {"listen": hearing.on_listen, "hold": hearing.on_hold},
        "hearing",
    ).serve_forever()


if __name__ == "__main__":
    main()
