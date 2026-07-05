"""
Integration tests for long-running service plugins.

Validates that processes survive across WAITING → READY cycles,
coordinate via mailboxes, and complete a multi-phase orchestration.
"""

from __future__ import annotations

import pytest

from emergence.core.state import ProcessState
from emergence.kernel.boot_context import build_long_running_services


@pytest.mark.integration
class TestLongRunningServices:
    def test_orchestrator_drives_services_to_completion(self):
        kernel = build_long_running_services()
        kernel.run()

        ctx = kernel.context
        assert ctx.state.get("orchestrator_status") == "completed"
        assert ctx.state.get("heartbeat") is not None
        assert int(ctx.state.get("events_collected", 0)) >= 3

        waiting = [
            p
            for p in ctx.process_table.all()
            if p.state in (ProcessState.WAITING, ProcessState.BLOCKED)
        ]
        assert waiting == []

        completed = [
            p
            for p in ctx.process_table.all()
            if p.state == ProcessState.COMPLETED
        ]
        assert len(completed) >= 1
