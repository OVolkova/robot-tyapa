from unittest.mock import MagicMock, patch

from tyapa_speech.__main__ import Speech


def _speech_with_mock_models() -> Speech:
    speech = Speech.__new__(Speech)
    speech.models = MagicMock()
    speech.models.synthesize.return_value = b"RIFF....WAVEfmt "
    return speech


def test_on_say_plays_audio_and_reports_spoken_s():
    speech = _speech_with_mock_models()
    with patch("tyapa_speech.__main__.play_wav_bytes") as mock_play:
        reply = speech.on_say({"text": "Woof!"})
    speech.models.synthesize.assert_called_once_with("Woof!")
    mock_play.assert_called_once()
    assert reply["ok"] is True
    assert reply["spoken_s"] >= 0


def test_on_say_empty_text_skips_synthesis():
    speech = _speech_with_mock_models()
    with patch("tyapa_speech.__main__.play_wav_bytes") as mock_play:
        reply = speech.on_say({"text": "   "})
    speech.models.synthesize.assert_not_called()
    mock_play.assert_not_called()
    assert reply["ok"] is True
    assert reply["spoken_s"] == 0


def test_main_serves_say_command():
    from tyapa_speech.__main__ import main

    with (
        patch("tyapa_speech.__main__.setup_logging"),
        patch("tyapa_speech.__main__.Speech") as speech_cls,
        patch("tyapa_speech.__main__.Server") as server,
    ):
        main()
    assert server.call_args.args[1] == {"say": speech_cls.return_value.on_say}
    server.return_value.serve_forever.assert_called_once()


def test_suppress_stderr_restores_fd2():
    import os

    from tyapa_speech import _suppress_stderr

    before = os.fstat(2)
    with _suppress_stderr():
        pass
    after = os.fstat(2)
    assert (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)
