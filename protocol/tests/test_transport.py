import threading

import pytest

from tyapa_protocol import messages as m
from tyapa_protocol.transport import Client, Server, ServiceUnavailable


def _serve(addr, n):
    srv = Server(addr, {"echo": lambda msg: (m.ok(text=msg["text"]), b"blob")}, "test")
    for _ in range(n):
        srv.serve_once(100)
    srv.sock.close(linger=0)


def test_roundtrip_blob_and_errors():
    addr = "tcp://127.0.0.1:5599"
    threading.Thread(target=_serve, args=(addr, 30), daemon=True).start()
    c = Client(addr, "test", timeout_s=2)
    assert c.call("ping")["ok"] is True
    reply, blob = c.call_blob("echo", text="hi")
    assert reply["text"] == "hi"
    assert blob == b"blob"
    assert c.call("nope")["ok"] is False  # unknown command → error reply
    assert c.call("echo")["ok"] is False  # handler crash → error reply, server survives
    assert c.call("ping")["ok"] is True


def test_timeout_then_recovers():
    addr = "tcp://127.0.0.1:5598"
    c = Client(addr, "late", timeout_s=0.2)
    with pytest.raises(ServiceUnavailable):
        c.call("ping")  # nobody there yet
    threading.Thread(target=_serve, args=(addr, 30), daemon=True).start()
    assert c.call("ping", timeout_s=2)["ok"] is True  # same client works once the service is up


def test_unserialisable_or_non_dict_handler_result_still_gets_a_reply():
    addr = "tcp://127.0.0.1:5597"
    handlers = {"bad": lambda msg: {"x": object()}, "none": lambda msg: None}

    def serve():
        srv = Server(addr, handlers, "test")
        for _ in range(30):
            srv.serve_once(100)
        srv.sock.close(linger=0)

    threading.Thread(target=serve, daemon=True).start()
    c = Client(addr, "test", timeout_s=2)
    assert c.call("bad")["ok"] is False  # not JSON-serialisable -> error reply, no crash
    assert c.call("none")["ok"] is False  # None is not a reply dict
    assert c.call("ping")["ok"] is True  # server survived both
