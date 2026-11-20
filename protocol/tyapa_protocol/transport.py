"""Thin ZeroMQ wrappers. Rule: a socket is only ever used by the thread that created it."""

import logging

import zmq

from . import messages as m

log = logging.getLogger(__name__)
_ctx = zmq.Context.instance()


class ServiceUnavailable(Exception):
    """The other service didn't answer in time (not running, busy, or crashed)."""


class Publisher:
    """Broadcasts events. Nobody listening = messages are simply dropped."""

    def __init__(self, addr: str):
        self.sock = _ctx.socket(zmq.PUB)
        self.sock.bind(addr)

    def publish(self, topic: str, msg: dict) -> None:
        self.sock.send_multipart([topic.encode(), m.encode(msg)])


class Subscriber:
    def __init__(self, addr: str, *topics: str):
        self.sock = _ctx.socket(zmq.SUB)
        self.sock.connect(addr)
        for t in topics or ("",):
            self.sock.setsockopt(zmq.SUBSCRIBE, t.encode())

    def recv(self, timeout_ms: int | None = None) -> dict | None:
        """Next event, or None if nothing arrived within timeout_ms."""
        if timeout_ms is not None and not self.sock.poll(timeout_ms):
            return None
        _topic, raw = self.sock.recv_multipart()
        return m.decode(raw)


class Server:
    """Answers commands. handlers: {"say": fn(msg) -> reply_dict | (reply_dict, bytes)}."""

    def __init__(self, addr: str, handlers: dict, name: str):
        self.name = name
        self.handlers = {"ping": lambda msg: m.ok(service=name), **handlers}
        self.sock = _ctx.socket(zmq.REP)
        self.sock.bind(addr)

    def serve_once(self, timeout_ms: int = 100) -> bool:
        if not self.sock.poll(timeout_ms):
            return False
        raw = self.sock.recv()
        try:
            msg = m.decode(raw)
            handler = self.handlers.get(msg.get("type"))
            result = handler(msg) if handler else m.error(f"unknown command {msg.get('type')!r}")
        except Exception as e:  # a REP socket MUST always reply, even on errors
            log.exception("%s: command failed", self.name)
            result = m.error(f"{type(e).__name__}: {e}")
        if isinstance(result, tuple):
            reply, blob = result
            self.sock.send_multipart([m.encode(reply), blob])
        else:
            self.sock.send(m.encode(result))
        return True

    def serve_forever(self, tick=None, tick_ms: int = 100) -> None:
        """Serve commands; call tick() at least every tick_ms (for timers/watchdogs)."""
        while True:
            self.serve_once(tick_ms)
            if tick:
                tick()


class Client:
    """Sends commands and waits for the reply ("lazy pirate": a stuck socket is replaced)."""

    def __init__(self, addr: str, name: str, timeout_s: float = 2.0):
        self.addr, self.name, self.timeout_s = addr, name, timeout_s
        self.sock = None
        self._connect()

    def _connect(self) -> None:
        if self.sock is not None:
            self.sock.close(linger=0)
        self.sock = _ctx.socket(zmq.REQ)
        self.sock.setsockopt(zmq.LINGER, 0)
        self.sock.connect(self.addr)

    def call_blob(
        self, type_: str, timeout_s: float | None = None, **fields
    ) -> tuple[dict, bytes | None]:
        t = self.timeout_s if timeout_s is None else timeout_s
        self.sock.send(m.encode(m.make(type_, **fields)))
        if not self.sock.poll(int(t * 1000)):
            self._connect()  # a REQ socket that missed its reply is stuck forever — replace it
            raise ServiceUnavailable(f"{self.name}: no reply to {type_!r} within {t:.1f}s")
        parts = self.sock.recv_multipart()
        return m.decode(parts[0]), (parts[1] if len(parts) > 1 else None)

    def call(self, type_: str, timeout_s: float | None = None, **fields) -> dict:
        return self.call_blob(type_, timeout_s, **fields)[0]
