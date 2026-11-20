"""Where every service listens. One place to change ports."""

import os

# Clients connect here. Set TYAPA_HOST=robot-tyapa.local to drive the Pi's services from the laptop.
CONNECT_HOST = os.getenv("TYAPA_HOST", "127.0.0.1")
# Services bind here. 127.0.0.1 = only programs on the Pi can talk to them (safe default).
# There is no authentication: binding 0.0.0.0 lets anyone on the LAN move the robot (act/raw).
BIND_HOST = os.getenv("TYAPA_BIND", "127.0.0.1")

HEARING_EVENTS = 5551  # PUB  hearing → brain: speech_ended, heard
HEARING_CMD = 5552  # REP  brain → hearing: listen, hold
SPEECH_CMD = 5553  # REP  brain → speech:  say
BODY_CMD = 5561  # REP  brain → body:    act, raw, stop, state
CAMERA_CMD = 5571  # REP  brain → camera:  frame   (camera guide, later)


def connect_addr(port: int) -> str:
    return f"tcp://{CONNECT_HOST}:{port}"


def bind_addr(port: int) -> str:
    return f"tcp://{BIND_HOST}:{port}"
