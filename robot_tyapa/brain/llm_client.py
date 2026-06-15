import json
import os
from abc import ABC, abstractmethod

from robot_tyapa.robot.petoi_commands import PETOI_COMMANDS as COMMANDS

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
