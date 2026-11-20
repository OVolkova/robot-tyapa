import logging

import pytest

from tyapa_protocol import endpoints as ep
from tyapa_protocol import messages as m
from tyapa_protocol import setup_logging


def test_make_ok_error_shapes():
    msg = m.make("x", a=1)
    assert msg["v"] == m.PROTOCOL_VERSION and msg["type"] == "x" and msg["a"] == 1
    assert m.ok(b=2)["ok"] is True
    err = m.error("boom")
    assert err["ok"] is False and err["error"] == "boom"


def test_encode_decode_roundtrip():
    msg = m.make("x", a=1)
    assert m.decode(m.encode(msg)) == msg


@pytest.mark.parametrize(
    "raw", [b"not json", b"[1, 2]", b'{"v": 99, "type": "x"}', b'{"type": "x"}']
)
def test_decode_rejects_bad_messages(raw):
    with pytest.raises(m.ProtocolError):
        m.decode(raw)


def test_endpoint_addresses():
    assert ep.connect_addr(ep.BODY_CMD) == f"tcp://{ep.CONNECT_HOST}:{ep.BODY_CMD}"
    assert ep.bind_addr(ep.BODY_CMD) == f"tcp://{ep.BIND_HOST}:{ep.BODY_CMD}"
    ports = [ep.HEARING_EVENTS, ep.HEARING_CMD, ep.SPEECH_CMD, ep.BODY_CMD, ep.CAMERA_CMD]
    assert len(set(ports)) == len(ports)


def test_setup_logging_configures_root(monkeypatch):
    seen = {}
    monkeypatch.setattr(logging, "basicConfig", lambda **kw: seen.update(kw))
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    setup_logging()
    assert seen["level"] == "DEBUG"
