"""LLM client, system prompt, tool schema, and conversation history."""

import json
import logging
import os
from abc import ABC, abstractmethod

from tyapa_protocol.commands import PETOI_COMMANDS as COMMANDS

logger = logging.getLogger(__name__)

_MAX_HISTORY = 10
_KEEP_RECENT = 4

_COMMANDS_SUMMARY = "\n".join(f"  {k}: {v}" for k, v in COMMANDS.items())

SYSTEM_PROMPT = f"""You are the brain of a robot dog named Tyapa. You are friendly, playful, and physically aware.

Keep responses short and natural — you speak aloud via text-to-speech.

The user interacts with you by voice. Each message includes the robot's current physical action in brackets. You may trigger a new physical action using the `perform_action` tool to move, express emotion, or react physically to the conversation.

Available robot actions:
{_COMMANDS_SUMMARY}

Rules:
- Always reply with spoken text (it will be played through the speaker).
- Use `perform_action` freely — to move when asked, to express emotions, or to react physically to what is being said.
- Gaits (wkF, trF, etc.) loop until stopped — mention if you are starting or stopping movement.
- Keep spoken responses under two sentences.
"""

PERFORM_ACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "perform_action",
        "description": (
            "Speak and optionally perform a physical action on the robot body. "
            "Always provide spoken_text. Use action to move, do a trick, or react physically."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "spoken_text": {
                    "type": "string",
                    "description": "What Tyapa says aloud",
                },
                "action": {
                    "type": "string",
                    "enum": list(COMMANDS.keys()),
                    "description": "Skill key to execute on the robot",
                },
            },
            "required": ["spoken_text"],
        },
    },
}


class LLMClient(ABC):
    @abstractmethod
    def complete(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> tuple[str, str | None]:
        """Returns (response_text, action_key | None)."""


class OpenAILLMClient(LLMClient):
    def __init__(self, model: str = "gpt-5.4-nano", api_key: str | None = None):
        from openai import OpenAI

        self.model = model
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY environment variable is not set")
        self.client = OpenAI(api_key=api_key)

    def complete(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> tuple[str, str | None]:
        kwargs: dict = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        response_text = message.content or ""
        action_key: str | None = None

        if message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call.function.name == "perform_action":
                    args = json.loads(tool_call.function.arguments)
                    action_key = args.get("action")
                    if not response_text:
                        response_text = args.get("spoken_text", "")
                    break

        return response_text, action_key


class AnthropicLLMClient(LLMClient):
    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None):
        raise NotImplementedError("Anthropic provider not yet implemented")

    def complete(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> tuple[str, str | None]:
        raise NotImplementedError


def create_llm_client(
    provider: str | None = None,
    model: str | None = None,
    **kwargs,
) -> LLMClient:
    provider = provider or os.environ.get("LLM_PROVIDER", "openai")
    model = model or os.environ.get("LLM_MODEL", "gpt-5.4-nano")

    if provider == "openai":
        return OpenAILLMClient(model=model, **kwargs)
    if provider == "anthropic":
        return AnthropicLLMClient(model=model, **kwargs)
    raise ValueError(f"Unknown LLM provider: {provider!r}. Supported: openai, anthropic")


class TextToText:
    def __init__(self, provider: str | None = None, model: str | None = None):
        self.llm = create_llm_client(provider=provider, model=model)
        self.history: list[dict] = []

    def _maybe_summarize(self) -> None:
        if len(self.history) < _MAX_HISTORY:
            return
        to_summarize = self.history[:-_KEEP_RECENT]
        recent = self.history[-_KEEP_RECENT:]
        summary_text, _ = self.llm.complete(
            [
                {
                    "role": "system",
                    "content": (
                        "Summarise the following robot-dog conversation in 2-3 sentences. "
                        "Note topics discussed and any physical actions the robot performed."
                    ),
                },
                *to_summarize,
                {"role": "user", "content": "Summarise the conversation above briefly."},
            ]
        )
        self.history = [
            {
                "role": "system",
                "content": f"Summary of earlier conversation: {summary_text or 'Previous exchanges occurred.'}",
            },
            *recent,
        ]
        logger.info("[TextToText] History summarised -> %d messages kept", len(self.history))

    def generate(self, user_text: str, current_action: str = "balance") -> tuple[str, str | None]:
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history)
        messages.append(
            {"role": "user", "content": f"[Current robot action: {current_action}]\n{user_text}"}
        )
        logger.info(
            "[TextToText] Sending to LLM: %d messages, user_text=%r", len(messages), user_text
        )
        response_text, action_key = self.llm.complete(messages, tools=[PERFORM_ACTION_TOOL])
        logger.info("[TextToText] LLM: text=%r, action=%r", response_text, action_key)
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": response_text or ""})
        self._maybe_summarize()
        return response_text, action_key


class Mind:
    def __init__(self, provider: str | None = None, model: str | None = None):
        self.provider = provider
        self.text_to_text = TextToText(provider=provider, model=model)

    def reply(self, content: str, current_action: str | None) -> tuple[str, str | None]:
        """Returns (text to say, bare skill key or None) — e.g. ("OK!", "sit").
        The action is the bare key straight from the LLM's tool call; prefixing
        it with "k" is the body service's job, not the brain's."""
        return self.text_to_text.generate(content, current_action or "balance")
