"""Integration tests for Timeline & Narrative API (M23)."""

from __future__ import annotations

import pytest

from emergence.admin.client import AdminClient
from emergence.events.narrative import build_timeline
from emergence.kernel.boot_context import build_research_assistant, create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.kernel.runtime import RuntimeService
from emergence.persistence.flush import flush_persistence
from tests.helpers_admin import short_data_dir


@pytest.mark.integration
class TestTimelineIntegration:
    def test_research_assistant_timeline_aggregates_findings(self):
        kernel, goal = build_research_assistant("quantum computing")
        kernel.run()

        timeline = build_timeline(kernel.context, goal_id=goal.goal_id)
        narratives = [
            entry["narrative"]
            for group in timeline["groups"]
            for entry in group["entries"]
        ]

        assert any("stored" in text.lower() for text in narratives)
        assert any("Research Assistant" in text for text in narratives)

    def test_timeline_survives_restart(self, monkeypatch):
        data_dir = short_data_dir("timeline-persist")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        ctx1 = create_kernel_context(persist=True)
        kernel1 = Kernel(
            ctx=ctx1,
            executor=ctx1.executor,
            lifecycle=LifecycleManager(),
        )
        goal = kernel1.create_goal("Persisted timeline")
        flush_persistence(ctx1)
        ctx1.checkpoints.close()

        ctx2 = create_kernel_context(persist=True)
        try:
            timeline = build_timeline(ctx2, goal_id=goal.goal_id)
            narratives = [
                entry["narrative"]
                for group in timeline["groups"]
                for entry in group["entries"]
            ]
            assert "Goal created: Persisted timeline" in narratives
        finally:
            ctx2.checkpoints.close()

    def test_admin_goal_timeline_endpoint(self, monkeypatch):
        data_dir = short_data_dir("timeline-admin")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        service = RuntimeService.start()
        try:
            goal = service.kernel.create_goal("Timeline admin goal")

            client = AdminClient.connect()
            payload = client.call(
                "goal.timeline",
                params={"goal_id": str(goal.goal_id)},
            )
            assert payload["goal_id"] == str(goal.goal_id)
            assert isinstance(payload["groups"], list)
            assert payload["scheduled"] == []
            narratives = [
                entry["narrative"]
                for group in payload["groups"]
                for entry in group["entries"]
            ]
            assert "Goal created: Timeline admin goal" in narratives
        finally:
            service.stop()
