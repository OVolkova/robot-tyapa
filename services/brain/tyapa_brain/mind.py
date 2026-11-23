"""LLM client, system prompt, tool schema, and conversation history."""

import json
import logging
import os
from abc import ABC, abstractmethod

from tyapa_protocol.commands import PETOI_COMMANDS as COMMANDS
from tyapa_protocol.commands import STAND_ACTION

logger = logging.getLogger(__name__)

_MAX_HISTORY = 10  # messages kept before older ones are summarised
_KEEP_RECENT = 4  # most recent messages kept verbatim when summarising

_COMMANDS_SUMMARY = "\n".join(f"  {k}: {v}" for k, v in COMMANDS.items())

SYSTEM_PROMPT = (
    "You are the brain of a robot dog named Tyapa. "
    "You are friendly, playful, and physically aware.\n\n"
    "You speak aloud via text-to-speech, so keep replies natural.\n\n"
    "The user interacts with you by voice. "
    "Each message includes the robot's current physical action in brackets. "
    "You may trigger a new physical action using the `perform_action` tool "
    "to move, express emotion, or react physically to the conversation.\n\n"
    "Available robot actions:\n"
    f"{_COMMANDS_SUMMARY}\n\n"
    "Rules:\n"
    "- Always reply with spoken text (it will be played through the speaker).\n"
    "- Use `perform_action` freely: to move when asked, express emotion, "
    "or react physically.\n"
    "- Gaits (wkF, trF, etc.) loop until stopped "
    "— mention if you are starting or stopping movement.\n"
    "- Keep spoken responses under two sentences.\n"
)

PERFORM_ACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "perform_action",
        "description": (
            "Speak and optionally perform a physical action on the robot body. "
            "Use action to move, do a trick, or react physically."
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
        """Return (response text, skill key or None)."""


class OpenAILLMClient(LLMClient):
    def __init__(self, model: str, api_key: str | None = None):
        from openai import OpenAI

        self.model = model
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable is not set")
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
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except ValueError:
                        logger.warning("Malformed perform_action arguments; ignoring the tool call")
                        break
                    if not isinstance(args, dict):
                        break
                    action_key = args.get("action")
                    if action_key not in COMMANDS:
                        if action_key is not None:
                            logger.warning("LLM asked for unknown action %r; ignoring", action_key)
                        action_key = None
                    if not response_text:
                        response_text = args.get("spoken_text", "")
                    break

        return response_text, action_key


def create_llm_client(provider: str, model: str, **kwargs) -> LLMClient:
    if provider == "openai":
        return OpenAILLMClient(model=model, **kwargs)
    raise ValueError(f"Unknown LLM provider: {provider!r}. Supported: openai")


class Mind:
    """One conversation: system prompt + rolling history, answered by an LLM."""

    def __init__(self, provider: str, model: str):
        self.llm = create_llm_client(provider=provider, model=model)
        self.history: list[dict] = []

    def reply(self, user_text: str, current_action: str | None) -> tuple[str, str | None]:
        """Return (text to say, bare skill key or None). The body adds the "k" prefix."""
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history)
        action_note = f"[Current robot action: {current_action or STAND_ACTION}]"
        messages.append({"role": "user", "content": f"{action_note}\n{user_text}"})
        logger.info("Sending to LLM: %d messages, user_text=%r", len(messages), user_text)
        response_text, action_key = self.llm.complete(messages, tools=[PERFORM_ACTION_TOOL])
        logger.info("LLM: text=%r, action=%r", response_text, action_key)
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": response_text or ""})
        return response_text, action_key

    def compact(self) -> None:
        """Summarise old history; call after the reply was spoken (it costs an LLM round-trip)."""
        try:
            self._summarize_if_needed()
        except Exception:
            logger.exception("history summarisation failed; keeping full history")

    def _summarize_if_needed(self) -> None:
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
        summary = summary_text or "Previous exchanges occurred."
        self.history = [
            {"role": "system", "content": f"Summary of earlier conversation: {summary}"},
            *recent,
        ]
        logger.info("History summarised -> %d messages kept", len(self.history))
