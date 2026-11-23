"""Brain service: listens for what was heard, decides, tells body and speech what to do."""

import logging
import time

from tyapa_protocol import endpoints as ep
from tyapa_protocol import setup_logging
from tyapa_protocol.messages import ProtocolError
from tyapa_protocol.transport import Client, ServiceUnavailable, Subscriber

from . import config
from .mind import Mind

log = logging.getLogger("tyapa.brain")


class Brain:
    def __init__(self):
        self.mind = Mind(provider=config.LLM_PROVIDER, model=config.LLM_MODEL)
        self.hearing = Client(ep.connect_addr(ep.HEARING_CMD), "hearing", timeout_s=5)
        self.speech = Client(ep.connect_addr(ep.SPEECH_CMD), "speech", timeout_s=60)
        self.body = Client(ep.connect_addr(ep.BODY_CMD), "body", timeout_s=2)
        self.events = Subscriber(ep.connect_addr(ep.HEARING_EVENTS), "hearing")

    # Helpers never raise: one missing service must not kill the brain.
    def act(self, action: str, duration_s: float | None = None) -> bool:
        try:
            r = self.body.call("act", action=action, duration_s=duration_s)
        except (ServiceUnavailable, ProtocolError) as e:
            log.warning("%s", e)
            return False
        if not r["ok"]:
            log.warning("body refused %r: %s", action, r.get("error"))
        return r["ok"]

    def current_action(self) -> str | None:
        try:
            return self.body.call("state").get("current_action")
        except (ServiceUnavailable, ProtocolError):
            return None

    def say(self, text: str, listen_after: bool = True) -> None:
        """Speak (blocking), then re-open the mic: speech and hearing are separate services."""
        try:
            if text:
                self.speech.call("say", text=text, timeout_s=60)
            if listen_after:
                self.hearing.call("listen")
        except (ServiceUnavailable, ProtocolError) as e:
            log.warning("%s", e)

    def handle_heard(self, ev: dict) -> None:
        text = ev["text"]
        t0 = time.monotonic()
        reply, action = self.mind.reply(text, self.current_action())
        log.info(
            "utt %s: %r -> say %r, action %r (llm %.2fs)",
            ev["utt"],
            text,
            reply,
            action,
            time.monotonic() - t0,
        )
        if action:
            self.act(action)
        self.say(reply)

    def run(self) -> None:
        log.info("Tyapa online. Listening...")
        self.say("", listen_after=True)  # (re)start listening, e.g. after a brain restart
        while True:
            try:
                ev = self.events.recv(timeout_ms=1000)
            except ProtocolError as e:
                log.warning("bad event: %s", e)
                continue
            if ev is None or ev["type"] != "heard":
                continue
            try:
                self.handle_heard(ev)
            except Exception:
                log.exception("turn failed")
                self.say("Sorry, my brain hiccupped.")


def main():
    setup_logging()
    Brain().run()


if __name__ == "__main__":
    main()
