"""
Shared runtime helpers for long-running EmergenceOS plugins.

Long-lived processes yield via wait_for_message() and resume
across scheduler wakeups. Working memory persists stage counters
and service state between executions.
"""

from __future__ import annotations

from emergence.common.message import Message
from emergence.common.request import Request
from emergence.common.response import Response
from emergence.core.process_context import ProcessContext
from emergence.memory.memory_category import MemoryCategory


STAGE_KEY = "__stage__"
EPISODIC_LOG_KEY = "event_log"


def get_stage(context: ProcessContext, default: int = 0) -> int:
    value = context.memory.retrieve(STAGE_KEY, default=default)
    return int(value) if value is not None else default


def set_stage(context: ProcessContext, stage: int) -> None:
    context.memory.store(STAGE_KEY, stage)


def increment_stage(context: ProcessContext) -> int:
    stage = get_stage(context) + 1
    set_stage(context, stage)
    return stage


def drain_messages(context: ProcessContext) -> list[Message]:
    messages: list[Message] = []
    while context.mailboxes.pending() > 0:
        message = context.mailboxes.receive()
        if message is not None:
            messages.append(message)
    return messages


def respond(
    context: ProcessContext,
    request: Request,
    result: object,
    *,
    success: bool = True,
) -> None:
    context.mailboxes.send(
        Response(
            sender_pid=str(context.process_id),
            recipient_pid=request.sender_pid,
            payload={"result": result},
            correlation_id=request.correlation_id,
            result=result,
            success=success,
        )
    )


def append_episodic(
    context: ProcessContext,
    entry: dict,
) -> None:
    log = context.memory.retrieve(
        EPISODIC_LOG_KEY,
        category=MemoryCategory.EPISODIC,
        default=[],
    )
    if not isinstance(log, list):
        log = []
    log.append(entry)
    context.memory.store(
        EPISODIC_LOG_KEY,
        log,
        category=MemoryCategory.EPISODIC,
    )


def is_shutdown(message: Message) -> bool:
    if isinstance(message, Request) and message.action == "shutdown":
        return True
    return getattr(message, "topic", None) == "shutdown"
