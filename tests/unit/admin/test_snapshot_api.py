"""
Unit tests for admin snapshot serialization.
"""

from __future__ import annotations

import pytest

from emergence.admin.snapshot_api import (
    build_admin_snapshot,
    system_snapshot_from_admin,
)
from emergence.core.event import Event, EventType
from emergence.core.process_definition import ProcessDefinition
from emergence.events.user_events import UserApprovalRequestedEvent
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager


@pytest.mark.unit
class TestAdminSnapshotApi:
    def test_build_admin_snapshot_includes_processes_and_state(self):
        ctx = create_kernel_context()
        kernel = Kernel(ctx=ctx, executor=ctx.executor, lifecycle=LifecycleManager())
        definition = ProcessDefinition(
            name="worker",
            implementation="worker",
            version="1.0.0",
        )
        ctx.registry.register(definition)
        kernel.spawn(definition)

        data = build_admin_snapshot(kernel)

        assert data["os_status"] is None
        assert len(data["processes"]) == 1
        assert data["processes"][0]["name"] == "worker"
        assert "budgets" in data
        assert "metrics" in data
        assert "pending_approvals" in data

    def test_pending_approvals_excludes_granted_requests(self):
        ctx = create_kernel_context()
        kernel = Kernel(ctx=ctx, executor=ctx.executor, lifecycle=LifecycleManager())

        ctx.event_bus.publish(
            UserApprovalRequestedEvent(
                request_id="req-1",
                message="publish report?",
                payload={
                    "request_id": "req-1",
                    "message": "publish report?",
                },
            )
        )
        ctx.state.set("approval:req-2", True)
        ctx.event_bus.publish(
            UserApprovalRequestedEvent(
                request_id="req-2",
                message="already granted",
                payload={
                    "request_id": "req-2",
                    "message": "already granted",
                },
            )
        )

        data = build_admin_snapshot(kernel)
        pending_ids = {item["request_id"] for item in data["pending_approvals"]}

        assert pending_ids == {"req-1"}

    def test_system_snapshot_from_admin_round_trip(self):
        ctx = create_kernel_context()
        kernel = Kernel(ctx=ctx, executor=ctx.executor, lifecycle=LifecycleManager())
        definition = ProcessDefinition(
            name="demo",
            implementation="demo",
            version="1.0.0",
        )
        ctx.registry.register(definition)
        kernel.spawn(definition)

        admin_data = build_admin_snapshot(kernel)
        snapshot = system_snapshot_from_admin(admin_data)

        assert snapshot.process_count == 1
        assert snapshot.processes[0].name == "demo"
