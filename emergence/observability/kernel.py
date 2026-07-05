from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from emergence.core.event import Event, EventType
from emergence.core.ids import ProcessID
from emergence.core.state import ProcessState
from emergence.events.event_store import EventStore


@dataclass(frozen=True, slots=True)
class LogEntry:
    timestamp: datetime
    process_id: str | None
    correlation_id: str | None
    event_type: str
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


class StructuredLogger:
    """
    Per-process structured log correlated by process_id
    and correlation_id.
    """

    def __init__(self) -> None:
        self._entries: list[LogEntry] = []

    def log_event(self, event: Event) -> None:
        self._entries.append(
            LogEntry(
                timestamp=event.timestamp,
                process_id=(
                    str(event.source_process)
                    if event.source_process
                    else None
                ),
                correlation_id=(
                    str(event.correlation_id)
                    if event.correlation_id
                    else None
                ),
                event_type=event.event_type.value,
                message=f"{event.event_type.value}",
                payload=dict(event.payload),
            )
        )

    def entries(
        self,
        *,
        process_id: ProcessID | None = None,
        correlation_id: UUID | None = None,
    ) -> list[LogEntry]:
        results = list(self._entries)
        if process_id is not None:
            pid = str(process_id)
            results = [e for e in results if e.process_id == pid]
        if correlation_id is not None:
            cid = str(correlation_id)
            results = [
                e for e in results if e.correlation_id == cid
            ]
        return results

    def clear(self) -> None:
        self._entries.clear()


@dataclass
class SystemMetrics:
    process_count_by_state: dict[str, int] = field(
        default_factory=dict
    )
    scheduler_depth: int = 0
    event_throughput: int = 0
    token_consumption: int = 0
    waiting_count: int = 0


class MetricsCollector:
    """Collects runtime metrics from kernel services."""

    def collect(self, kernel) -> SystemMetrics:
        ctx = kernel.context
        counts: dict[str, int] = {}

        for process in ctx.process_table.all():
            state = process.state.value
            counts[state] = counts.get(state, 0) + 1

        token_total = sum(
            ctx.budgets.usage(p.process_id).tokens
            for p in ctx.process_table.all()
        )

        return SystemMetrics(
            process_count_by_state=counts,
            scheduler_depth=len(ctx.scheduler),
            event_throughput=ctx.event_store.count(),
            token_consumption=token_total,
            waiting_count=len(ctx.scheduler.waiting_ids()),
        )


class TraceAPI:
    """
    Returns the causal chain for a correlation_id from the event log.
    """

    def __init__(self, event_store: EventStore) -> None:
        self._store = event_store

    def trace(self, correlation_id: UUID) -> list[Event]:
        return self._store.query(correlation_id=correlation_id)

    def audit_process(self, process_id: ProcessID) -> list[Event]:
        return self._store.query(source_process=process_id)


class ObservabilityKernel:
    """
    Unified observability surface: logs, metrics, and tracing.
    """

    def __init__(
        self,
        event_store: EventStore,
        event_bus,
    ) -> None:
        self.logger = StructuredLogger()
        self.metrics = MetricsCollector()
        self.trace = TraceAPI(event_store)
        self._event_store = event_store

        for event_type in EventType:
            event_bus.subscribe(event_type, self.logger.log_event)

    @property
    def event_store(self) -> EventStore:
        return self._event_store
