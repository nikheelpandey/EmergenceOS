"""Unit tests for GoalPolicy."""

from __future__ import annotations

import pytest

from emergence.cognitive.goal_policy import (
    SPEND_PRESETS,
    GoalPolicy,
    resolve_goal_policy,
)


@pytest.mark.unit
class TestGoalPolicy:
    def test_spend_presets_exist(self):
        assert SPEND_PRESETS["low"].max_tokens < SPEND_PRESETS["high"].max_tokens

    def test_resolve_from_presets(self):
        policy = resolve_goal_policy(
            mode="research",
            spend_preset="low",
            autonomy_preset="ask",
        )
        assert policy.spend_preset == "low"
        assert policy.auto_approve is False
        assert policy.budget.max_tokens == SPEND_PRESETS["low"].max_tokens

    def test_research_defaults_to_auto_approve(self):
        policy = resolve_goal_policy(mode="research")
        assert policy.autonomy_preset == "auto"
        assert policy.auto_approve is True

    def test_autonomy_auto(self):
        policy = resolve_goal_policy(mode="goal", autonomy_preset="auto")
        assert policy.auto_approve is True

    def test_round_trip_dict(self):
        original = resolve_goal_policy(
            mode="worker",
            spend_preset="high",
            autonomy_preset="ask",
            config={"topic": "quantum"},
        )
        restored = GoalPolicy.from_dict(original.to_dict())
        assert restored.workload == "worker"
        assert restored.spend_preset == "high"
        assert restored.config["topic"] == "quantum"
