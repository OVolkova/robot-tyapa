"""Hand-poke services: just cli --help"""

import argparse
import itertools
import sys
import threading
import time

from tyapa_protocol import endpoints as ep
from tyapa_protocol import messages as m
from tyapa_protocol.messages import ProtocolError
from tyapa_protocol.transport import Client, Publisher, Server, ServiceUnavailable, Subscriber

# Services that answer commands (brain only listens; camera is reserved, not built yet).
SERVICES = {
    "hearing": ep.HEARING_CMD,
    "speech": ep.SPEECH_CMD,
    "body": ep.BODY_CMD,
}


def client(name: str, timeout_s: float = 5.0) -> Client:
    return Client(ep.connect_addr(SERVICES[name]), name, timeout_s=timeout_s)


def show(reply: dict) -> None:
    print({k: v for k, v in reply.items() if k not in ("v", "ts")})


def cmd_ping(a: argparse.Namespace) -> None:
    for name in SERVICES:
        try:
            r = client(name, 1.0).call("ping")
            print(f"{name:7s} OK   {r.get('status', '')}")
        except ServiceUnavailable:
            print(f"{name:7s} --   not running")


def cmd_say(a: argparse.Namespace) -> None:
    show(client("speech", 60).call("say", text=a.text))


def cmd_listen(a: argparse.Namespace) -> None:
    show(client("hearing").call("listen"))


def cmd_hold(a: argparse.Namespace) -> None:
    show(client("hearing").call("hold"))


def cmd_act(a: argparse.Namespace) -> None:
    show(client("body").call("act", action=a.action, duration_s=a.seconds))


def cmd_raw(a: argparse.Namespace) -> None:
    show(client("body").call("raw", cmd=a.cmd))


def cmd_stop(a: argparse.Namespace) -> None:
    show(client("body").call("stop"))


def cmd_state(a: argparse.Namespace) -> None:
    show(client("body").call("state"))


def cmd_events(a: argparse.Namespace) -> None:  # pragma: no cover - infinite interactive loop
    sub = Subscriber(ep.connect_addr(ep.HEARING_EVENTS), "hearing")
    print("waiting for hearing events — speak to the dog (Ctrl-C to stop)")
    while True:
        try:
            ev = sub.recv()
        except ProtocolError as e:
            print(f"bad event: {e}")
            continue
        print(f"{ev['type']:13s}", {k: v for k, v in ev.items() if k not in ("v", "type", "ts")})


def cmd_fake_voice(a: argparse.Namespace) -> None:  # pragma: no cover - interactive
    """Fake hearing + speech: typed lines are published as speech_ended/heard; say() is printed."""

    def serve():
        def on_say(msg):
            print(f"\n  dog says: {msg['text']}\n> ", end="", flush=True)
            return m.ok(spoken_s=0)

        hearing = Server(
            ep.bind_addr(ep.HEARING_CMD),
            {"listen": lambda msg: m.ok(), "hold": lambda msg: m.ok()},
            "fake-hearing",
        )
        speech = Server(ep.bind_addr(ep.SPEECH_CMD), {"say": on_say}, "fake-speech")
        while True:
            hearing.serve_once(10)
            speech.serve_once(10)

    threading.Thread(target=serve, daemon=True).start()
    pub = Publisher(ep.bind_addr(ep.HEARING_EVENTS))
    print("fake voice: type what you'd say to the dog, Enter to send (Ctrl-D to quit)")
    for utt in itertools.count(1):
        try:
            text = input("> ")
        except EOFError:
            break
        if text.strip():
            t = time.monotonic()
            pub.publish("hearing", m.make("speech_ended", utt=utt, t_end=t))
            pub.publish("hearing", m.make("heard", utt=utt, text=text.strip(), t_end=t, stt_s=0.0))


def main() -> int:
    p = argparse.ArgumentParser(prog="tyapa")
    sub = p.add_subparsers(required=True)
    sub.add_parser("ping", help="which services are running").set_defaults(fn=cmd_ping)
    s = sub.add_parser("say", help="make the dog speak")
    s.add_argument("text")
    s.set_defaults(fn=cmd_say)
    sub.add_parser("listen", help="re-open the mic").set_defaults(fn=cmd_listen)
    sub.add_parser("hold", help="keep the mic closed").set_defaults(fn=cmd_hold)
    s = sub.add_parser("act", help="send a skill, e.g. sit")
    s.add_argument("action")
    s.add_argument("--seconds", type=float, default=None, help="gaits: stop after this long")
    s.set_defaults(fn=cmd_act)
    s = sub.add_parser("raw", help="joint move, e.g. 'm0 40'")
    s.add_argument("cmd")
    s.set_defaults(fn=cmd_raw)
    sub.add_parser("stop", help="stand still (balance)").set_defaults(fn=cmd_stop)
    sub.add_parser("state", help="what the body is doing").set_defaults(fn=cmd_state)
    sub.add_parser("events", help="print what the hearing service hears").set_defaults(
        fn=cmd_events
    )
    sub.add_parser("fake-voice", help="type instead of talking (laptop testing)").set_defaults(
        fn=cmd_fake_voice
    )
    a = p.parse_args()
    try:
        a.fn(a)
    except (ServiceUnavailable, ProtocolError) as e:
        print(f"error: {e} — is it running?  (just status)", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
