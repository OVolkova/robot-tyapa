import itertools
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from tyapa_hearing.__main__ import Hearing, main


def _hearing() -> Hearing:
    h = Hearing.__new__(Hearing)
    h.models = MagicMock()
    h.models.transcribe.return_value = "  hello dog  "
    h.listening = threading.Event()
    h.last_cmd = time.monotonic()
    h.utt_ids = itertools.count(1)
    return h


def _types(events: MagicMock) -> list[str]:
    return [c.args[1]["type"] for c in events.publish.call_args_list]


def test_on_listen_opens_mic_and_on_hold_closes_it():
    h = _hearing()
    assert h.on_listen({})["ok"] is True
    assert h.listening.is_set()
    assert h.on_hold({})["ok"] is True
    assert not h.listening.is_set()


def test_capture_once_publishes_speech_ended_then_heard():
    h, events = _hearing(), MagicMock()
    h.listening.set()
    with patch("tyapa_hearing.__main__.capture_with_vad", return_value=b"wav"):
        h._capture_once(events)
    assert _types(events) == ["speech_ended", "heard"]
    assert events.publish.call_args.args[1]["text"] == "hello dog"
    assert not h.listening.is_set()  # half-duplex: closed until the brain says listen


def test_capture_once_empty_transcript_reopens_mic_without_heard():
    h, events = _hearing(), MagicMock()
    h.models.transcribe.return_value = "   "
    h.listening.set()
    with patch("tyapa_hearing.__main__.capture_with_vad", return_value=b"wav"):
        h._capture_once(events)
    assert _types(events) == ["speech_ended"]
    assert h.listening.is_set()


def test_capture_once_no_speech_publishes_nothing():
    h, events = _hearing(), MagicMock()
    h.listening.set()
    with patch("tyapa_hearing.__main__.capture_with_vad", return_value=None):
        h._capture_once(events)
    events.publish.assert_not_called()


def test_capture_once_reopens_mic_after_brain_timeout():
    h, events = _hearing(), MagicMock()
    h.listening = MagicMock()
    h.listening.wait.return_value = False
    h.last_cmd = time.monotonic() - 1000
    h._capture_once(events)
    h.listening.set.assert_called_once()


def test_capture_once_stays_closed_before_timeout():
    h, events = _hearing(), MagicMock()
    h.listening = MagicMock()
    h.listening.wait.return_value = False
    h._capture_once(events)
    h.listening.set.assert_not_called()


def test_capture_loop_survives_exceptions_and_reopens_mic():
    """Regression: an exception used to kill the capture thread, leaving a deaf service."""
    h = _hearing()
    h._capture_once = MagicMock(side_effect=[RuntimeError("mic busy"), KeyboardInterrupt])
    with (
        patch("tyapa_hearing.__main__.Publisher"),
        patch("tyapa_hearing.__main__.time.sleep") as sleep,
        pytest.raises(KeyboardInterrupt),  # BaseException: only way out of the infinite loop
    ):
        h.capture_loop()
    assert h._capture_once.call_count == 2  # kept going after the error
    sleep.assert_called_once_with(2)
    assert h.listening.is_set()


def test_main_starts_capture_thread_and_serves():
    with (
        patch("tyapa_hearing.__main__.setup_logging"),
        patch("tyapa_hearing.__main__.Hearing") as hearing_cls,
        patch("tyapa_hearing.__main__.threading.Thread") as thread,
        patch("tyapa_hearing.__main__.Server") as server,
    ):
        main()
    thread.assert_called_once()
    thread.return_value.start.assert_called_once()
    hearing_cls.return_value.listening.set.assert_called_once()
    server.return_value.serve_forever.assert_called_once()
