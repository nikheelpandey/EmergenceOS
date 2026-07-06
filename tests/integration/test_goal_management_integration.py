"""Integration tests for goal management API."""

from __future__ import annotations

import json
import urllib.request

import pytest

from emergence.core.ids import GoalID
from emergence.ingress.goal_management import archive_goal, rerun_goal, update_goal
from emergence.ingress.goal_submission import submit_goal
from emergence.kernel.boot_context import build_kernel
from emergence.kernel.runtime import RuntimeService
from tests.helpers_admin import short_data_dir


@pytest.mark.integration
class TestGoalManagementIntegration:
    def test_update_archive_rerun(self, monkeypatch):
        data_dir = short_data_dir("goal-manage")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        kernel = build_kernel(spawn=None, load_plugins=False)
        created = submit_goal(
            kernel,
            "Manage me",
            mode="goal",
            spend_preset="low",
            autonomy_preset="ask",
        )
        goal_id = created.goal_id

        updated = update_goal(
            kernel,
            goal_id,
            description="Updated description",
            spend_preset="high",
        )
        assert updated["description"] == "Updated description"
        assert updated["policy"]["spend_preset"] == "high"

        archived = archive_goal(kernel, goal_id)
        assert archived["archived"] is True
        record = kernel.context.goal_registry.get(GoalID.from_string(goal_id))
        assert record is not None
        assert record.archived is True

    def test_rerun_research_goal(self, monkeypatch):
        data_dir = short_data_dir("goal-rerun")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        kernel = build_kernel(spawn=None, load_plugins=True)
        created = submit_goal(
            kernel,
            "Rerun topic",
            mode="research",
            spend_preset="medium",
            autonomy_preset="auto",
        )
        result = rerun_goal(kernel, created.goal_id)
        assert result["status"] == "rerunning"
        assert result["process_id"] is not None

    def test_http_goal_management(self, monkeypatch):
        data_dir = short_data_dir("goal-manage-http")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))
        monkeypatch.setenv("EMERGENCE_HTTP_PORT", "0")

        service = RuntimeService.start()
        try:
            base = service.http.base_url()

            def request_json(url, *, method="GET", body=None):
                data = json.dumps(body).encode() if body is not None else None
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method=method,
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return json.loads(resp.read().decode())

            created = request_json(
                f"{base}/goals",
                method="POST",
                body={
                    "description": "HTTP manage",
                    "mode": "goal",
                    "spend_preset": "low",
                    "autonomy_preset": "ask",
                },
            )
            goal_id = created["goal_id"]

            patched = request_json(
                f"{base}/goals/{goal_id}",
                method="PATCH",
                body={"description": "Patched title"},
            )
            assert patched["description"] == "Patched title"

            cancelled = request_json(
                f"{base}/goals/{goal_id}/cancel",
                method="POST",
            )
            assert cancelled["status"] == "cancelled"

            deleted = request_json(
                f"{base}/goals/{goal_id}",
                method="DELETE",
            )
            assert deleted["archived"] is True
        finally:
            service.stop()
