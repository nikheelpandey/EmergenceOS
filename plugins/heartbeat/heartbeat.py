"""
Heartbeat monitor — a long-running service process.

Each scheduler wakeup:
  1. Drains mailbox (ping → respond, shutdown → stop)
  2. Records a heartbeat beat in working memory
  3. Creates an explicit checkpoint
  4. Yields to WAITING until the next message
"""

from __future__ import annotations

from datetime import UTC, datetime

from emergence.apps.long_running_runtime import (
    drain_messages,
    get_stage,
    increment_stage,
    is_shutdown,
    respond,
)
from emergence.common.request import Request
from emergence.core.process_context import ProcessContext
from emergence.memory.memory_category import MemoryCategory


def run(context: ProcessContext) -> str:
    for message in drain_messages(context):
        if is_shutdown(message):
            context.state.set("heartbeat_status", "stopped")
            return "heartbeat_stopped"

        if isinstance(message, Request) and message.action == "ping":
            beat = get_stage(context)
            respond(context, message, {"beat": beat, "alive": True})

    beat = increment_stage(context)
    now = datetime.now(UTC).isoformat()

    context.memory.store("last_beat", beat)
    context.memory.store("last_beat_at", now)
    context.state.set("heartbeat", f"beat={beat} at {now}")

    context.checkpoints.create()

    max_beats = int(context.state.get("max_beats", 100))
    if max_beats > 0 and beat >= max_beats:
        context.state.set("heartbeat_status", "max_beats_reached")
        return "heartbeat_finished"

    context.wait_for_message()
    return "heartbeat_waiting"
