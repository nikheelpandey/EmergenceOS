"""
Event collector — accumulates notifications into episodic memory.

Runs until it receives a flush/shutdown command, then returns
the collected event count.
"""

from __future__ import annotations

from emergence.apps.long_running_runtime import (
    EPISODIC_LOG_KEY,
    append_episodic,
    drain_messages,
    is_shutdown,
)
from emergence.common.notification import Notification
from emergence.core.process_context import ProcessContext
from emergence.memory.memory_category import MemoryCategory


def run(context: ProcessContext) -> str:
    for message in drain_messages(context):
        if is_shutdown(message):
            count = _event_count(context)
            context.state.set("events_collected", count)
            return f"collector_stopped:{count}"

        if isinstance(message, Notification):
            append_episodic(
                context,
                {
                    "topic": message.topic,
                    "data": message.data,
                    "from": message.sender_pid,
                },
            )
            total = _event_count(context)
            context.state.set("events_collected", total)

    context.wait_for_message()
    return "collector_waiting"


def _event_count(context: ProcessContext) -> int:
    log = context.memory.retrieve(
        EPISODIC_LOG_KEY,
        category=MemoryCategory.EPISODIC,
        default=[],
    )
    return len(log) if isinstance(log, list) else 0
