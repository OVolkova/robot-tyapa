import sys
from unittest.mock import MagicMock, patch

import pytest

from tyapa_protocol import cli
from tyapa_protocol.transport import ServiceUnavailable


def _run(argv: list[str], client: MagicMock) -> int:
    with patch.object(sys, "argv", ["tyapa", *argv]), patch.object(cli, "client", client):
        return cli.main()


def test_ping_reports_running_and_missing_services(capsys):
    def fake_client(name, timeout_s=5.0):
        c = MagicMock()
        if name == "speech":
            c.call.side_effect = ServiceUnavailable("speech: down")
        else:
            c.call.return_value = {"ok": True, "status": "fine"}
        return c

    assert _run(["ping"], MagicMock(side_effect=fake_client)) == 0
    out = capsys.readouterr().out
    assert "hearing" in out
    assert "speech" in out
    assert "not running" in out
    assert "camera" not in out  # reserved, never running


@pytest.mark.parametrize(
    ("argv", "service", "call"),
    [
        (["say", "hi"], "speech", ("say", {"text": "hi"})),
        (["act", "sit"], "body", ("act", {"action": "sit", "duration_s": None})),
        (["act", "wkF", "--seconds", "2"], "body", ("act", {"action": "wkF", "duration_s": 2.0})),
        (["raw", "m0 40"], "body", ("raw", {"cmd": "m0 40"})),
        (["stop"], "body", ("stop", {})),
        (["state"], "body", ("state", {})),
        (["listen"], "hearing", ("listen", {})),
        (["hold"], "hearing", ("hold", {})),
    ],
)
def test_commands_route_to_the_right_service(argv, service, call):
    client = MagicMock()
    client.return_value.call.return_value = {"ok": True}
    assert _run(argv, client) == 0
    assert client.call_args.args[0] == service
    client.return_value.call.assert_called_once_with(call[0], **call[1])


def test_unavailable_service_exits_nonzero(capsys):
    client = MagicMock()
    client.return_value.call.side_effect = ServiceUnavailable("body: no reply")
    assert _run(["state"], client) == 1
    assert "is it running" in capsys.readouterr().err
