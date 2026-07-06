"""Integration tests for goal policy."""

from __future__ import annotations

import json
import urllib.request

import pytest

from emergence.core.ids import GoalID
from emergence.ingress.goal_submission import submit_goal
from emergence.kernel.boot_context import build_kernel
from emergence.kernel.runtime import RuntimeService
from tests.helpers_admin import short_data_dir


@pytest.mark.integration
class TestGoalPolicyIntegration:
    def test_submit_goal_stores_policy(self, monkeypatch):
        data_dir = short_data_dir("goal-policy")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        kernel = build_kernel(spawn=None, load_plugins=False)
        result = submit_goal(
            kernel,
            "Policy test goal",
            mode="goal",
            spend_preset="low",
            autonomy_preset="ask",
        )

        goal_id = GoalID.from_string(result.goal_id)
        record = kernel.context.goal_registry.get(goal_id)
        assert record is not None
        assert record.policy is not None
        assert record.policy.spend_preset == "low"
        assert record.policy.auto_approve is False

        usage = kernel.context.goal_registry.policy_usage(goal_id)
        assert usage is not None
        assert usage["limits"]["max_tokens"] == record.policy.budget.max_tokens

    def test_http_policy_endpoint(self, monkeypatch):
        data_dir = short_data_dir("goal-policy-http")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))
        monkeypatch.setenv("EMERGENCE_HTTP_PORT", "0")

        service = RuntimeService.start()
        try:
            base = service.http.base_url()
            body = json.dumps({
                "description": "HTTP policy goal",
                "mode": "goal",
                "spend_preset": "medium",
                "autonomy_preset": "ask",
            }).encode()
            req = urllib.request.Request(
                f"{base}/goals",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                created = json.loads(resp.read().decode())

            with urllib.request.urlopen(
                f"{base}/goals/{created['goal_id']}/policy",
                timeout=5,
            ) as resp:
                policy = json.loads(resp.read().decode())

            assert policy["spend_preset"] == "medium"
            assert policy["limits"]["max_tokens"] > 0
        finally:
            service.stop()

    def test_policy_persists_in_snapshot(self, monkeypatch):
        data_dir = short_data_dir("goal-policy-persist")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        kernel = build_kernel(spawn=None, load_plugins=False, persist=True)
        result = submit_goal(
            kernel,
            "Persist policy",
            mode="goal",
            spend_preset="high",
            autonomy_preset="auto",
        )
        snapshot = kernel.context.goal_registry.snapshot()
        assert snapshot["entries"][0]["policy"]["spend_preset"] == "high"

        kernel.context.goal_registry.restore(snapshot)
        restored = kernel.context.goal_registry.get(
            GoalID.from_string(result.goal_id)
        )
        assert restored is not None
        assert restored.policy is not None
        assert restored.policy.spend_preset == "high"
