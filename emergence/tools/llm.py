"""
LLM tool provider — Ollama, OpenAI-compatible, and mock adapters.

Processes invoke LLMs only through the ``llm.chat`` tool registered
in the kernel ToolRegistry. No plugin imports provider SDKs directly.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from emergence.core.ids import ProcessID


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Structured response from an LLM provider."""

    content: str
    tokens_used: int
    model: str
    provider: str
    cost_usd: float = 0.0

    def as_tool_result(self) -> dict[str, Any]:
        """Return a dict the ToolExecutor unwraps for budget accounting."""
        return {
            "content": self.content,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
            "model": self.model,
            "provider": self.provider,
        }


class LLMProvider(Protocol):
    """Protocol for LLM backend adapters."""

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        ...


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (4 chars per token)."""
    return max(1, len(text) // 4)


def _extract_topic(prompt: str) -> str | None:
    """Pull the research subject from common prompt patterns."""
    quoted = re.search(r"'([^']+)'", prompt)
    if quoted:
        return quoted.group(1).strip()

    for pattern in (
        r"research thoroughly:\s*(.+?)(?:\n|$)",
        r"research (?:the )?topic (?:of )?(.+?)(?:\n|$)",
        r"report on\s+(.+?)(?:\s+from|\n|$)",
    ):
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            topic = match.group(1).strip().rstrip(".")
            if topic:
                return topic

    return None


class MockLLMProvider:
    """
    Deterministic LLM for tests and offline demos.

    Recognizes prompt patterns and returns canned JSON/text responses.
    """

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        prompt = messages[-1]["content"] if messages else ""
        content = self._respond(prompt)
        tokens = _estimate_tokens(prompt) + _estimate_tokens(content)
        return LLMResponse(
            content=content,
            tokens_used=tokens,
            model=model or "mock",
            provider="mock",
        )

    def _respond(self, prompt: str) -> str:
        lower = prompt.lower()
        topic = _extract_topic(prompt)

        if "task" in lower and ("json" in lower or "decompose" in lower or "plan" in lower):
            return json.dumps([
                {
                    "name": "research",
                    "process_definition_name": "researcher",
                    "dependencies": [],
                    "priority": 5,
                    "expected_output": (
                        f"Research findings on {topic}"
                        if topic
                        else "Research findings on the topic"
                    ),
                },
                {
                    "name": "evaluate",
                    "process_definition_name": "evaluator",
                    "dependencies": ["research"],
                    "priority": 3,
                    "expected_output": "Quality evaluation of research",
                },
                {
                    "name": "report",
                    "process_definition_name": "researcher",
                    "dependencies": ["evaluate"],
                    "priority": 2,
                    "expected_output": "Final research report",
                },
            ])

        if "evaluate" in lower or "score" in lower:
            subject = topic or "the research"
            return json.dumps({
                "score": 8,
                "feedback": (
                    f"Thorough research with good coverage of {subject}."
                ),
                "approved": True,
            })

        if "report" in lower or "summarize" in lower or "synthesize" in lower:
            title = topic or "the requested topic"
            return (
                f"# Research Report: {title}\n\n"
                f"This report synthesizes findings on **{title}**.\n\n"
                f"## Overview\n"
                f"- Background and historical context of {title}\n"
                f"- Major contributions, influence, and legacy\n"
                f"- Key themes relevant to the research goal\n\n"
                f"## Summary\n"
                f"Research on {title} completed using episodic memory "
                f"and LLM synthesis. Configure a real LLM provider "
                f"(`EMERGENCE_LLM_PROVIDER=ollama` or `openai`) for "
                f"detailed, factual output.\n"
            )

        if "research" in lower or "investigate" in lower or "topic" in lower:
            subject = topic or "the requested topic"
            return (
                f"Research findings on {subject}:\n"
                f"- Historical background and defining characteristics\n"
                f"- Major events, ideas, or contributions associated with "
                f"{subject}\n"
                f"- Lasting impact and contemporary relevance\n"
                f"\n(Using mock LLM — set EMERGENCE_LLM_PROVIDER for "
                f"real research.)"
            )

        return f"Mock LLM response to: {prompt[:120]}"


class OllamaProvider:
    """Adapter for the Ollama local inference server."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3.2",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        resolved_model = model or self._default_model
        payload = json.dumps({
            "model": resolved_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }).encode()

        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Ollama request failed: {exc}. "
                "Is Ollama running at "
                f"{self._base_url}?"
            ) from exc

        content = data.get("message", {}).get("content", "")
        prompt_text = " ".join(m["content"] for m in messages)
        tokens = _estimate_tokens(prompt_text) + _estimate_tokens(content)

        return LLMResponse(
            content=content,
            tokens_used=tokens,
            model=resolved_model,
            provider="ollama",
        )


class OpenAICompatibleProvider:
    """Adapter for OpenAI and OpenAI-compatible APIs."""

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        default_model: str = "gpt-4o-mini",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or os.environ.get("EMERGENCE_LLM_API_KEY", "")
        self._default_model = default_model

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        if not self._api_key:
            raise RuntimeError(
                "OpenAI API key not configured. "
                "Set EMERGENCE_LLM_API_KEY environment variable."
            )

        resolved_model = model or self._default_model
        payload = json.dumps({
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature,
        }).encode()

        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        tokens = usage.get("total_tokens", 0) or (
            _estimate_tokens(" ".join(m["content"] for m in messages))
            + _estimate_tokens(content)
        )

        return LLMResponse(
            content=content,
            tokens_used=tokens,
            model=resolved_model,
            provider="openai",
            cost_usd=tokens * 0.000002,
        )


def create_llm_provider() -> LLMProvider:
    """
    Factory that selects an LLM provider from environment variables.

    EMERGENCE_LLM_PROVIDER: mock (default), ollama, openai
    EMERGENCE_LLM_MODEL: model name override
    EMERGENCE_LLM_BASE_URL: API base URL override
    EMERGENCE_LLM_API_KEY: API key for OpenAI-compatible providers
    """
    provider = os.environ.get("EMERGENCE_LLM_PROVIDER", "mock").lower()
    model = os.environ.get("EMERGENCE_LLM_MODEL")
    base_url = os.environ.get("EMERGENCE_LLM_BASE_URL")

    if provider == "ollama":
        return OllamaProvider(
            base_url=base_url or "http://localhost:11434",
            default_model=model or "llama3.2",
        )

    if provider in ("openai", "openai_compatible"):
        return OpenAICompatibleProvider(
            base_url=base_url or "https://api.openai.com/v1",
            default_model=model or "gpt-4o-mini",
        )

    return MockLLMProvider()


def create_llm_chat_handler(
    provider: LLMProvider | None = None,
) -> Any:
    """Return a ToolRegistry handler for ``llm.chat``."""

    llm = provider or create_llm_provider()

    def handler(
        args: dict[str, Any],
        process_id: ProcessID | None = None,
    ) -> dict[str, Any]:
        messages = args.get("messages")
        if messages is None:
            prompt = args.get("prompt", "")
            system = args.get("system", "")
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

        response = llm.chat(
            messages,
            model=args.get("model"),
            temperature=float(args.get("temperature", 0.7)),
        )
        return response.as_tool_result()

    return handler
