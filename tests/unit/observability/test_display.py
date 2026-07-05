"""
Tests for emergence.observability.display.
"""

from __future__ import annotations

from datetime import UTC, datetime

from emergence.core.state import ProcessState
from emergence.observability.display import (
    format_process_table,
    format_scheduler_view,
    format_top_screen,
)
from emergence.observability.snapshot import ProcessSnapshot, SystemSnapshot


def _snapshot() -> SystemSnapshot:
    return SystemSnapshot(
        captured_at=datetime(2026, 7, 5, 12, 0, 0, tzinfo=UTC),
        processes=(
            ProcessSnapshot(
                process_id="11111111-1111-1111-1111-111111111111",
                name="fast",
                state=ProcessState.COMPLETED,
                age_seconds=1.2,
                parent_id=None,
                scheduled=False,
                mailbox_pending=0,
                capability_count=0,
                failure_reason=None,
            ),
            ProcessSnapshot(
                process_id="22222222-2222-2222-2222-222222222222",
                name="pending",
                state=ProcessState.READY,
                age_seconds=0.4,
                parent_id=None,
                scheduled=True,
                mailbox_pending=0,
                capability_count=4,
                failure_reason=None,
            ),
        ),
        scheduler_depth=1,
        queued_process_ids=("22222222-2222-2222-2222-222222222222",),
        state_keys=("last_completed",),
    )


class TestDisplay:
    def test_format_process_table_includes_process_names(self):
        output = format_process_table(_snapshot())

        assert "fast" in output
        assert "pending" in output
        assert "completed" in output
        assert "ready" in output

    def test_format_scheduler_view_lists_queue(self):
        output = format_scheduler_view(_snapshot())

        assert "READY QUEUE" in output
        assert "22222222" in output

    def test_format_top_screen_combines_sections(self):
        output = format_top_screen(_snapshot())

        assert "EmergenceOS process monitor" in output
        assert "fast" in output
        assert "READY QUEUE" in output
