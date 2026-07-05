"""Tests for emergence.tools.llm — M13."""

from __future__ import annotations

import json

from emergence.core.ids import ProcessID
from emergence.tools.llm import MockLLMProvider, create_llm_chat_handler


class TestMockLLMProvider:
    def test_plan_decomposition_returns_json(self):
        provider = MockLLMProvider()
        response = provider.chat([
            {"role": "user", "content": "Decompose this goal into task JSON plan"},
        ])
        specs = json.loads(response.content)
        assert isinstance(specs, list)
        assert len(specs) >= 2
        assert specs[0]["name"] == "research"

    def test_research_prompt_returns_findings(self):
        provider = MockLLMProvider()
        response = provider.chat([
            {"role": "user", "content": "Research the topic of event-driven systems"},
        ])
        assert "Research findings" in response.content
        assert response.tokens_used > 0

    def test_evaluation_prompt_returns_json(self):
        provider = MockLLMProvider()
        response = provider.chat([
            {"role": "user", "content": "Evaluate and score this output"},
        ])
        data = json.loads(response.content)
        assert "score" in data
        assert "approved" in data


class TestLLMChatHandler:
    def test_handler_returns_tool_result_dict(self):
        handler = create_llm_chat_handler(MockLLMProvider())
        result = handler({"prompt": "Research topic X"}, ProcessID.new())
        assert "content" in result
        assert "tokens_used" in result
        assert result["tokens_used"] > 0
