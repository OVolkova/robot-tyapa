from unittest.mock import MagicMock

from tyapa_protocol.transport import ServiceUnavailable

from tyapa_brain.__main__ import Brain


def _brain_with_mocks() -> Brain:
    brain = Brain.__new__(Brain)
    brain.mind = MagicMock()
    brain.hearing = MagicMock()
    brain.speech = MagicMock()
    brain.body = MagicMock()
    brain.events = MagicMock()
    return brain


# -- say(): speak, then re-open the mic --


def test_say_calls_speech_then_reopens_hearing():
    brain = _brain_with_mocks()
    brain.say("Woof!")
    brain.speech.call.assert_called_once_with("say", text="Woof!", timeout_s=60)
    brain.hearing.call.assert_called_once_with("listen")


def test_say_empty_text_skips_speech_but_still_reopens_mic():
    brain = _brain_with_mocks()
    brain.say("")
    brain.speech.call.assert_not_called()
    brain.hearing.call.assert_called_once_with("listen")


def test_say_listen_after_false_does_not_reopen_mic():
    brain = _brain_with_mocks()
    brain.say("hold on", listen_after=False)
    brain.speech.call.assert_called_once()
    brain.hearing.call.assert_not_called()


def test_say_swallows_service_unavailable():
    brain = _brain_with_mocks()
    brain.speech.call.side_effect = ServiceUnavailable("speech: down")
    brain.say("hi")  # must not raise
    brain.hearing.call.assert_not_called()  # skipped after the speech call raised


# -- act() / current_action(): one missing service must not kill the brain ---


def test_act_returns_false_when_body_unavailable():
    brain = _brain_with_mocks()
    brain.body.call.side_effect = ServiceUnavailable("body: down")
    assert brain.act("sit") is False


def test_act_returns_false_when_body_rejects_action():
    brain = _brain_with_mocks()
    brain.body.call.return_value = {"ok": False, "error": "unknown action"}
    assert brain.act("moonwalk") is False


def test_current_action_returns_none_when_body_unavailable():
    brain = _brain_with_mocks()
    brain.body.call.side_effect = ServiceUnavailable("body: down")
    assert brain.current_action() is None


# -- handle_heard(): the full turn, order matters (act before say) -----------


def test_handle_heard_acts_then_says_in_order():
    brain = _brain_with_mocks()
    brain.mind.reply.return_value = ("Sitting!", "sit")
    brain.body.call.return_value = {"ok": True}
    calls = []
    brain.act = lambda action, duration_s=None: calls.append(("act", action))
    brain.say = lambda text, listen_after=True: calls.append(("say", text))

    brain.handle_heard({"utt": 1, "text": "sit down"})

    assert calls == [("act", "sit"), ("say", "Sitting!")]


def test_handle_heard_with_no_action_only_says():
    brain = _brain_with_mocks()
    brain.mind.reply.return_value = ("Hello!", None)
    calls = []
    brain.act = lambda action, duration_s=None: calls.append(("act", action))
    brain.say = lambda text, listen_after=True: calls.append(("say", text))

    brain.handle_heard({"utt": 1, "text": "hi"})

    assert calls == [("say", "Hello!")]
