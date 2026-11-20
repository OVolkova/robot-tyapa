"""Message format shared by every service: small JSON dicts with a type and a version."""

import json
import time

PROTOCOL_VERSION = 1


class ProtocolError(Exception):
    """A message that isn't valid tyapa protocol (bad JSON or wrong version)."""


def make(type_: str, **fields) -> dict:
    # monotonic: only comparable between processes on the same machine, not across TYAPA_HOST
    return {"v": PROTOCOL_VERSION, "type": type_, "ts": time.monotonic(), **fields}


def ok(**fields) -> dict:
    return make("ok", ok=True, **fields)


def error(text: str) -> dict:
    return make("error", ok=False, error=text)


def encode(msg: dict) -> bytes:
    return json.dumps(msg, separators=(",", ":")).encode()


def decode(raw: bytes) -> dict:
    try:
        msg = json.loads(raw)
    except ValueError as e:
        raise ProtocolError(f"not JSON: {e}") from e
    if not isinstance(msg, dict) or msg.get("v") != PROTOCOL_VERSION:
        raise ProtocolError(
            f"protocol version {msg.get('v') if isinstance(msg, dict) else '?'} "
            f"!= {PROTOCOL_VERSION}"
        )
    return msg
