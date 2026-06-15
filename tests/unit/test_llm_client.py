import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from robot_tyapa.brain.llm_client import (
    PERFORM_ACTION_TOOL,
    SYSTEM_PROMPT,
    AnthropicLLMClient,
    OpenAILLMClient,
    create_llm_client,
)
from robot_tyapa.robot.petoi_commands import PETOI_COMMANDS

# ── tool schema ───────────────────────────────────────────────────────────────


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


# ── factory ───────────────────────────────────────────────────────────────────


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


# ── OpenAILLMClient ───────────────────────────────────────────────────────────


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
