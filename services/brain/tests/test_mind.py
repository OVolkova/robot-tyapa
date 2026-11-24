import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from tyapa_brain.mind import (
    _KEEP_RECENT,
    _MAX_HISTORY,
    PERFORM_ACTION_TOOL,
    SYSTEM_PROMPT,
    Mind,
    OpenAILLMClient,
    create_llm_client,
)
from tyapa_protocol.commands import PETOI_COMMANDS

# -- tool schema -------------------------------------------------------------


def test_perform_action_tool_enum_covers_all_commands():
    enum_values = PERFORM_ACTION_TOOL["function"]["parameters"]["properties"]["action"]["enum"]
    assert set(enum_values) == set(PETOI_COMMANDS.keys())


def test_perform_action_tool_spoken_text_is_required():
    required = PERFORM_ACTION_TOOL["function"]["parameters"]["required"]
    assert "spoken_text" in required
    assert "action" not in required


def test_system_prompt_mentions_perform_action():
    assert "perform_action" in SYSTEM_PROMPT


def test_system_prompt_lists_commands():
    for key in ["wkF", "sit", "hi"]:
        assert key in SYSTEM_PROMPT


# -- factory ------------------------------------------------------------------


def test_create_llm_client_builds_openai_client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with patch.dict(sys.modules, {"openai": MagicMock()}):
        client = create_llm_client(provider="openai", model="gpt-5.4-mini")
    assert isinstance(client, OpenAILLMClient)
    assert client.model == "gpt-5.4-mini"


def test_create_llm_client_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm_client(provider="banana", model="x", api_key="x")


# -- OpenAILLMClient ----------------------------------------------------------


def test_openai_client_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with (
        patch.dict(sys.modules, {"openai": MagicMock()}),
        pytest.raises(RuntimeError, match="OPENAI_API_KEY"),
    ):
        OpenAILLMClient(model="gpt-5.4-nano", api_key=None)


def _fake_client(
    content: str,
    tool_action: str | None = None,
    tool_spoken_text: str | None = None,
) -> OpenAILLMClient:
    message = MagicMock()
    message.content = content
    if tool_action or tool_spoken_text is not None:
        tc = MagicMock()
        tc.function.name = "perform_action"
        args: dict = {}
        if tool_action:
            args["action"] = tool_action
        if tool_spoken_text is not None:
            args["spoken_text"] = tool_spoken_text
        tc.function.arguments = json.dumps(args)
        message.tool_calls = [tc]
    else:
        message.tool_calls = None

    response = MagicMock()
    response.choices = [MagicMock(message=message)]

    client = OpenAILLMClient.__new__(OpenAILLMClient)
    client.model = "gpt-5.4-nano"
    client.client = MagicMock()
    client.client.chat.completions.create.return_value = response
    return client


def test_complete_text_only():
    client = _fake_client("Hello there!")
    text, action = client.complete([{"role": "user", "content": "hi"}])
    assert text == "Hello there!"
    assert action is None


def test_complete_with_action():
    client = _fake_client("Sitting down now!", tool_action="sit")
    text, action = client.complete(
        [{"role": "user", "content": "sit"}], tools=[PERFORM_ACTION_TOOL]
    )
    assert text == "Sitting down now!"
    assert action == "sit"


def test_complete_passes_tools_and_tool_choice_to_api():
    client = _fake_client("ok")
    client.complete([{"role": "user", "content": "go"}], tools=[PERFORM_ACTION_TOOL])
    kwargs = client.client.chat.completions.create.call_args[1]
    assert kwargs["tools"] == [PERFORM_ACTION_TOOL]
    assert kwargs["tool_choice"] == "auto"


def test_complete_no_tools_omits_tool_choice():
    client = _fake_client("ok")
    client.complete([{"role": "user", "content": "hi"}], tools=None)
    kwargs = client.client.chat.completions.create.call_args[1]
    assert "tool_choice" not in kwargs


def test_complete_action_with_no_content_uses_spoken_text_from_tool():
    client = _fake_client(None, tool_action="hi", tool_spoken_text="Hi! I'm Tyapa!")
    text, action = client.complete(
        [{"role": "user", "content": "what's your name?"}], tools=[PERFORM_ACTION_TOOL]
    )
    assert text == "Hi! I'm Tyapa!"
    assert action == "hi"


def test_complete_ignores_unknown_tool_calls():
    message = MagicMock()
    message.content = "text"
    tc = MagicMock()
    tc.function.name = "some_other_tool"
    tc.function.arguments = json.dumps({})
    message.tool_calls = [tc]
    response = MagicMock()
    response.choices = [MagicMock(message=message)]

    client = OpenAILLMClient.__new__(OpenAILLMClient)
    client.model = "gpt-5.4-nano"
    client.client = MagicMock()
    client.client.chat.completions.create.return_value = response

    _text, action = client.complete([{"role": "user", "content": "x"}])
    assert action is None


# -- Mind: conversation history -----------------------------------------


def _make_mind(llm_text: str = "Hello!", llm_action: str | None = None) -> Mind:
    tt = Mind.__new__(Mind)
    tt.llm = MagicMock()
    tt.llm.complete.return_value = (llm_text, llm_action)
    tt.history = []
    return tt


def test_history_empty_before_first_call():
    tt = _make_mind()
    assert len(tt.history) == 0


def test_history_has_two_entries_after_one_call():
    tt = _make_mind()
    tt.reply("hello", "balance")
    assert len(tt.history) == 2


def test_history_roles_alternate():
    tt = _make_mind()
    tt.reply("hello", "balance")
    roles = [m["role"] for m in tt.history]
    assert roles == ["user", "assistant"]


def test_history_summarised_when_full():
    tt = _make_mind()
    for _ in range(5):
        tt.reply("hello", "balance")
        tt.compact()
    assert len(tt.history) == _KEEP_RECENT + 1


def test_summary_message_is_system_role():
    tt = _make_mind()
    for _ in range(5):
        tt.reply("hello", "balance")
        tt.compact()
    assert tt.history[0]["role"] == "system"
    assert "Summary" in tt.history[0]["content"]


def test_summary_calls_llm_with_old_messages():
    tt = _make_mind()
    for _ in range(5):
        tt.reply("hello", "balance")
        tt.compact()
    _, last_call_kwargs = tt.llm.complete.call_args
    assert "tools" not in last_call_kwargs


def test_history_stays_bounded_across_multiple_summarisations():
    tt = _make_mind()
    for _ in range(12):
        tt.reply("hello", "balance")
        tt.compact()
    assert len(tt.history) < _MAX_HISTORY


def test_history_fed_into_subsequent_call():
    tt = _make_mind()
    tt.reply("hello", "balance")
    tt.reply("world", "sit")
    messages = tt.llm.complete.call_args[0][0]
    # system + 2 history entries + new user = 4
    assert len(messages) == 4


# -- Mind: LLM message construction -------------------------------------


def test_current_action_appears_in_user_message():
    tt = _make_mind()
    tt.reply("hello", "trF")
    messages = tt.llm.complete.call_args[0][0]
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "trF" in user_msg["content"]


def test_system_message_is_first():
    tt = _make_mind()
    tt.reply("hello", "balance")
    messages = tt.llm.complete.call_args[0][0]
    assert messages[0]["role"] == "system"


def test_mind_init():
    with patch("tyapa_brain.mind.create_llm_client") as mock_create:
        mind = Mind(provider="openai", model="gpt-5.4-nano")
    mock_create.assert_called_once_with(provider="openai", model="gpt-5.4-nano")
    assert mind.history == []


def test_reply_defaults_current_action_to_standing():
    mind = _make_mind()
    mind.reply("hi", None)
    user_msg = mind.llm.complete.call_args[0][0][-1]["content"]
    assert "[Current robot action: balance]" in user_msg


def test_compact_swallows_llm_failure_and_keeps_history():
    mind = _make_mind()
    for _ in range(5):
        mind.reply("hello", "balance")
    mind.llm.complete.side_effect = RuntimeError("boom")
    mind.compact()  # must not raise
    assert len(mind.history) == 10


def test_malformed_tool_arguments_keep_text_reply():
    client = _fake_client("hello", tool_action="sit")
    client.client.chat.completions.create.return_value.choices[0].message.tool_calls[
        0
    ].function.arguments = "{not json"
    assert client.complete([], tools=[]) == ("hello", None)


def test_unknown_action_from_llm_is_dropped():
    client = _fake_client("hello", tool_action="moonwalk123")
    assert client.complete([], tools=[]) == ("hello", None)


def test_generate_does_not_summarise_inline():
    tt = _make_mind()
    for _ in range(6):
        tt.reply("hello", "balance")
    assert tt.llm.complete.call_count == 6  # one call per turn, no summary call
    tt.compact()
    assert tt.llm.complete.call_count == 7
