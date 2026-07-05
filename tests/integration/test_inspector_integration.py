"""Integration tests for Event Inspector API (M24)."""

from __future__ import annotations

import pytest

from emergence.admin.client import AdminClient
from emergence.admin.snapshot_api import build_inspect_payload
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.kernel.runtime import RuntimeService
from tests.helpers_admin import short_data_dir


@pytest.mark.integration
class TestInspectorIntegration:
    def test_timeline_event_inspectable(self):
        ctx = create_kernel_context()
        kernel = Kernel(ctx=ctx, executor=ctx.executor, lifecycle=LifecycleManager())
        goal = kernel.create_goal("Inspector goal")

        from emergence.events.narrative import build_timeline

        timeline = build_timeline(ctx, goal_id=goal.goal_id)
        event_id = timeline["groups"][0]["entries"][0]["event_id"]
        payload = build_inspect_payload(kernel, event_id)

        assert payload["event_id"] == event_id
        assert payload["correlation_chain"] is not None
        assert "why" in payload

    def test_admin_event_inspect(self, monkeypatch):
        data_dir = short_data_dir("inspector-admin")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        service = RuntimeService.start()
        try:
            goal = service.kernel.create_goal("Admin inspect goal")
            client = AdminClient.connect()
            timeline = client.call(
                "goal.timeline",
                params={"goal_id": str(goal.goal_id)},
            )
            event_id = timeline["groups"][0]["entries"][0]["event_id"]
            inspected = client.call(
                "event.inspect",
                params={"event_id": event_id},
            )
            assert inspected["event_id"] == event_id
        finally:
            service.stop()
