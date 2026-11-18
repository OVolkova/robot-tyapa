import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from tyapa_protocol.commands import PETOI_COMMANDS

from tyapa_brain.mind import (
    _KEEP_RECENT,
    _MAX_HISTORY,
    PERFORM_ACTION_TOOL,
    SYSTEM_PROMPT,
    AnthropicLLMClient,
    Mind,
    OpenAILLMClient,
    TextToText,
    create_llm_client,
)

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


def test_create_llm_client_defaults_to_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with patch.dict(sys.modules, {"openai": MagicMock()}):
        client = create_llm_client()
    assert isinstance(client, OpenAILLMClient)
    assert client.model == "gpt-5.4-nano"


def test_create_llm_client_respects_env_vars(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-5.4-mini")
    with patch.dict(sys.modules, {"openai": MagicMock()}):
        client = create_llm_client()
    assert client.model == "gpt-5.4-mini"


def test_create_llm_client_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm_client(provider="banana", model="x", api_key="x")


def test_create_llm_client_anthropic_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        create_llm_client(provider="anthropic", model="x")


# -- OpenAILLMClient ----------------------------------------------------------


def test_openai_client_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch.dict(sys.modules, {"openai": MagicMock()}):
        with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
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


def test_anthropic_complete_raises_not_implemented():
    client = AnthropicLLMClient.__new__(AnthropicLLMClient)
    with pytest.raises(NotImplementedError):
        client.complete([])


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

    text, action = client.complete([{"role": "user", "content": "x"}])
    assert action is None


# -- TextToText: conversation history -----------------------------------------


def _make_text_to_text(llm_text: str = "Hello!", llm_action: str | None = None) -> TextToText:
    tt = TextToText.__new__(TextToText)
    tt.llm = MagicMock()
    tt.llm.complete.return_value = (llm_text, llm_action)
    tt.history = []
    return tt


def test_history_empty_before_first_call():
    tt = _make_text_to_text()
    assert len(tt.history) == 0


def test_history_has_two_entries_after_one_call():
    tt = _make_text_to_text()
    tt.generate("hello", "balance")
    assert len(tt.history) == 2


def test_history_roles_alternate():
    tt = _make_text_to_text()
    tt.generate("hello", "balance")
    roles = [m["role"] for m in tt.history]
    assert roles == ["user", "assistant"]


def test_history_summarised_when_full():
    tt = _make_text_to_text()
    for _ in range(5):
        tt.generate("hello", "balance")
    assert len(tt.history) == _KEEP_RECENT + 1


def test_summary_message_is_system_role():
    tt = _make_text_to_text()
    for _ in range(5):
        tt.generate("hello", "balance")
    assert tt.history[0]["role"] == "system"
    assert "Summary" in tt.history[0]["content"]


def test_summary_calls_llm_with_old_messages():
    tt = _make_text_to_text()
    for _ in range(5):
        tt.generate("hello", "balance")
    _, last_call_kwargs = tt.llm.complete.call_args
    assert "tools" not in last_call_kwargs


def test_history_stays_bounded_across_multiple_summarisations():
    tt = _make_text_to_text()
    for _ in range(12):
        tt.generate("hello", "balance")
    assert len(tt.history) < _MAX_HISTORY


def test_history_fed_into_subsequent_call():
    tt = _make_text_to_text()
    tt.generate("hello", "balance")
    tt.generate("world", "sit")
    messages = tt.llm.complete.call_args[0][0]
    # system + 2 history entries + new user = 4
    assert len(messages) == 4


# -- TextToText: LLM message construction -------------------------------------


def test_current_action_appears_in_user_message():
    tt = _make_text_to_text()
    tt.generate("hello", "trF")
    messages = tt.llm.complete.call_args[0][0]
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "trF" in user_msg["content"]


def test_system_message_is_first():
    tt = _make_text_to_text()
    tt.generate("hello", "balance")
    messages = tt.llm.complete.call_args[0][0]
    assert messages[0]["role"] == "system"


def test_text_to_text_init():
    with patch("tyapa_brain.mind.create_llm_client") as mock_create:
        tt = TextToText(provider="openai", model="gpt-5.4-nano")
    mock_create.assert_called_once_with(provider="openai", model="gpt-5.4-nano")
    assert tt.history == []


# -- Mind: thin wrapper (new code, replaces the old LocalBrain adapter) ------


def test_mind_reply_forwards_to_text_to_text_and_defaults_current_action():
    mind = Mind.__new__(Mind)
    mind.text_to_text = MagicMock()
    mind.text_to_text.generate.return_value = ("Sitting!", "sit")

    text, action = mind.reply("sit down", current_action=None)

    mind.text_to_text.generate.assert_called_once_with("sit down", "balance")
    assert (text, action) == ("Sitting!", "sit")


def test_mind_reply_passes_through_current_action():
    mind = Mind.__new__(Mind)
    mind.text_to_text = MagicMock()
    mind.text_to_text.generate.return_value = ("ok", None)

    mind.reply("stop", current_action="wkF")

    mind.text_to_text.generate.assert_called_once_with("stop", "wkF")
