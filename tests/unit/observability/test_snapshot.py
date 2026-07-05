"""
Tests for emergence.observability.snapshot.
"""

from __future__ import annotations

from emergence.core.state import ProcessState
from emergence.observability.demo import build_demo_kernel
from emergence.observability.snapshot import capture_system_snapshot


class TestCaptureSystemSnapshot:
    def test_demo_kernel_has_mixed_states(self):
        kernel = build_demo_kernel()
        snapshot = capture_system_snapshot(kernel)

        assert snapshot.process_count == 3
        assert snapshot.scheduler_depth == 1

        states = {process.state for process in snapshot.processes}
        assert ProcessState.COMPLETED in states
        assert ProcessState.FAILED in states
        assert ProcessState.READY in states

    def test_completed_process_has_no_mailbox_or_capabilities(self):
        kernel = build_demo_kernel()
        snapshot = capture_system_snapshot(kernel)

        completed = next(
            process
            for process in snapshot.processes
            if process.state == ProcessState.COMPLETED
        )

        assert completed.mailbox_pending == 0
        assert completed.capability_count == 0
        assert completed.scheduled is False

    def test_ready_process_is_scheduled(self):
        kernel = build_demo_kernel()
        snapshot = capture_system_snapshot(kernel)

        ready = next(
            process
            for process in snapshot.processes
            if process.state == ProcessState.READY
        )

        assert ready.scheduled is True
        assert ready.capability_count > 0

    def test_state_keys_include_demo_writes(self):
        kernel = build_demo_kernel()
        snapshot = capture_system_snapshot(kernel)

        assert "last_completed" in snapshot.state_keys
