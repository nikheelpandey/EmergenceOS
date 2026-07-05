from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from emergence.core.event import Event, EventType
from emergence.core.ids import GoalID, ProcessID
from emergence.core.state import ProcessState
from emergence.spaces.registry import DEFAULT_SPACE_ID

if TYPE_CHECKING:
    from emergence.kernel.context import KernelContext


class GoalKind(str, Enum):
  """Workload lifetime semantics."""

  ONE_SHOT = "one_shot"
  PERSISTENT = "persistent"


class GoalHealth(str, Enum):
  """Computed health from kernel signals — never LLM self-report."""

  HEALTHY = "healthy"
  DEGRADED = "degraded"
  NEEDS_ATTENTION = "needs_attention"
  IDLE = "idle"


@dataclass(slots=True)
class GoalStats:
  """Aggregate counters for a registered goal."""

  uptime_seconds: float = 0.0
  active_child_count: int = 0
  knowledge_size_bytes: int = 0
  last_event_at: datetime | None = None


@dataclass
class GoalRecord:
  """Durable registry entry for a living workload."""

  goal_id: GoalID
  description: str
  kind: GoalKind = GoalKind.ONE_SHOT
  root_process_id: ProcessID | None = None
  child_process_ids: set[str] = field(default_factory=set)
  registered_at: datetime = field(
      default_factory=lambda: datetime.now(UTC)
  )
  last_event_at: datetime | None = None
  pipeline_stage: str | None = None
  archived: bool = False
  has_process_failure: bool = False
  has_budget_exceeded: bool = False
  space_id: str = DEFAULT_SPACE_ID

  @property
  def all_process_ids(self) -> set[str]:
    ids = set(self.child_process_ids)
    if self.root_process_id is not None:
      ids.add(str(self.root_process_id))
    return ids


class GoalNotRegisteredError(Exception):
  pass


class GoalRegistry:
  """
  Durable, queryable store for goals as living workloads.

  Separate from CognitiveManager's in-memory orchestration dict.
  Health is computed from kernel signals at query time.
  """

  def __init__(
      self,
      event_bus: EventBus,
      *,
      staleness_seconds: float = 300.0,
      approval_threshold_seconds: float = 60.0,
  ) -> None:
    self._event_bus = event_bus
    self._staleness_seconds = staleness_seconds
    self._approval_threshold_seconds = approval_threshold_seconds
    self._records: dict[str, GoalRecord] = {}
    self._process_to_goal: dict[str, str] = {}
    self._last_health: dict[str, GoalHealth] = {}
    self._ctx: KernelContext | None = None
    self._subscribe()

  def bind_context(self, ctx: KernelContext) -> None:
    """Attach kernel services used for live health computation."""
    self._ctx = ctx

  def register(
      self,
      goal_id: GoalID,
      description: str,
      *,
      kind: GoalKind = GoalKind.ONE_SHOT,
      root_process_id: ProcessID | None = None,
  ) -> GoalRecord:
    key = str(goal_id)
    if key in self._records:
      record = self._records[key]
      record.description = description
      record.kind = kind
      if root_process_id is not None:
        record.root_process_id = root_process_id
        self._process_to_goal[str(root_process_id)] = key
      return record

    record = GoalRecord(
        goal_id=goal_id,
        description=description,
        kind=kind,
        root_process_id=root_process_id,
    )
    self._records[key] = record
    if root_process_id is not None:
      self._process_to_goal[str(root_process_id)] = key
    return record

  def associate_process(
      self,
      goal_id: GoalID,
      process_id: ProcessID,
      *,
      as_root: bool = False,
  ) -> None:
    record = self._require(goal_id)
    pid = str(process_id)
    record.child_process_ids.add(pid)
    self._process_to_goal[pid] = str(goal_id)
    if as_root or record.root_process_id is None:
      record.root_process_id = process_id
    self._touch(record)

  def goal_for_process(self, process_id: ProcessID) -> GoalID | None:
    goal_key = self._process_to_goal.get(str(process_id))
    if goal_key is None:
      return None
    return GoalID.from_string(goal_key)

  def get(self, goal_id: GoalID) -> GoalRecord | None:
    return self._records.get(str(goal_id))

  def list_all(self, *, include_archived: bool = False) -> list[GoalRecord]:
    records = list(self._records.values())
    if include_archived:
      return records
    return [record for record in records if not record.archived]

  def compute_health(self, record: GoalRecord) -> GoalHealth:
    if record.has_process_failure:
      return GoalHealth.DEGRADED
    if record.has_budget_exceeded:
      return GoalHealth.DEGRADED

    ctx = self._ctx
    if ctx is not None:
      for pid in record.all_process_ids:
        process_id = ProcessID.from_string(pid)
        if not ctx.process_table.exists(process_id):
          continue
        process = ctx.process_table.get(process_id)
        if process.state == ProcessState.FAILED:
          return GoalHealth.DEGRADED
        if not ctx.budgets.can_dispatch(process.process_id, process.budget):
          return GoalHealth.DEGRADED

      pending = _pending_approvals_for_goal(record, ctx)
      now = datetime.now(UTC)
      for approval in pending:
        age = (now - approval["timestamp"]).total_seconds()
        if age > self._approval_threshold_seconds:
          return GoalHealth.NEEDS_ATTENTION

    if record.last_event_at is not None:
      idle = (datetime.now(UTC) - record.last_event_at).total_seconds()
      if idle > self._staleness_seconds:
        return GoalHealth.IDLE

    return GoalHealth.HEALTHY

  def compute_stats(self, record: GoalRecord) -> GoalStats:
    now = datetime.now(UTC)
    uptime = (now - record.registered_at).total_seconds()
    active_children = 0
    knowledge_size = 0

    ctx = self._ctx
    if ctx is not None:
      for pid in record.all_process_ids:
        process_id = ProcessID.from_string(pid)
        if not ctx.process_table.exists(process_id):
          continue
        process = ctx.process_table.get(process_id)
        if not process.is_finished:
          active_children += 1

      knowledge_size = ctx.knowledge_index.total_bytes_for_goal(record.goal_id)

    return GoalStats(
        uptime_seconds=uptime,
        active_child_count=active_children,
        knowledge_size_bytes=knowledge_size,
        last_event_at=record.last_event_at,
    )

  def query(self, goal_id: GoalID) -> dict[str, Any] | None:
    record = self.get(goal_id)
    if record is None:
      return None
    return self._to_view(record)

  def set_space(self, goal_id: GoalID, space_id: str) -> None:
    record = self._require(goal_id)
    record.space_id = space_id

  def list_views(
      self,
      *,
      include_archived: bool = False,
      space_id: str | None = None,
  ) -> list[dict[str, Any]]:
    records = self.list_all(include_archived=include_archived)
    if space_id is not None:
      records = [record for record in records if record.space_id == space_id]
    return [self._to_view(record) for record in records]

  def sync_from_cognitive(self, cognitive) -> None:
    """Ensure cognitive goals have registry entries after restore."""
    for raw in cognitive.snapshot().get("goals", []):
      goal_id = GoalID.from_string(str(raw["goal_id"]))
      if str(goal_id) not in self._records:
        self.register(
            goal_id,
            str(raw["description"]),
            kind=GoalKind.ONE_SHOT,
        )

  def snapshot(self) -> dict[str, Any]:
    return {
        "entries": [
            {
                "goal_id": str(record.goal_id),
                "description": record.description,
                "kind": record.kind.value,
                "root_process_id": (
                    str(record.root_process_id)
                    if record.root_process_id is not None
                    else None
                ),
                "child_process_ids": sorted(record.child_process_ids),
                "registered_at": record.registered_at.isoformat(),
                "last_event_at": (
                    record.last_event_at.isoformat()
                    if record.last_event_at is not None
                    else None
                ),
                "pipeline_stage": record.pipeline_stage,
                "archived": record.archived,
                "has_process_failure": record.has_process_failure,
                "has_budget_exceeded": record.has_budget_exceeded,
                "space_id": record.space_id,
            }
            for record in self._records.values()
        ],
        "process_to_goal": self._process_to_goal,
    }

  def restore(self, data: dict[str, Any]) -> None:
    self._records.clear()
    self._process_to_goal.clear()

    for raw in data.get("entries", []):
      root_raw = raw.get("root_process_id")
      record = GoalRecord(
          goal_id=GoalID.from_string(str(raw["goal_id"])),
          description=str(raw["description"]),
          kind=GoalKind(str(raw.get("kind", GoalKind.ONE_SHOT.value))),
          root_process_id=(
              ProcessID.from_string(str(root_raw)) if root_raw is not None else None
          ),
          child_process_ids=set(raw.get("child_process_ids", [])),
          registered_at=datetime.fromisoformat(str(raw["registered_at"])),
          last_event_at=(
              datetime.fromisoformat(str(raw["last_event_at"]))
              if raw.get("last_event_at") is not None
              else None
          ),
          pipeline_stage=raw.get("pipeline_stage"),
          archived=bool(raw.get("archived", False)),
          has_process_failure=bool(raw.get("has_process_failure", False)),
          has_budget_exceeded=bool(raw.get("has_budget_exceeded", False)),
          space_id=str(raw.get("space_id", DEFAULT_SPACE_ID)),
      )
      self._records[str(record.goal_id)] = record

    self._process_to_goal = {
        str(pid): str(goal_id)
        for pid, goal_id in dict(data.get("process_to_goal", {})).items()
    }

  def _to_view(self, record: GoalRecord) -> dict[str, Any]:
    health = self.compute_health(record)
    stats = self.compute_stats(record)
    knowledge: dict[str, Any] = {}
    ctx = self._ctx
    if ctx is not None:
      knowledge = ctx.knowledge_index.summarize_goal(record.goal_id)
    return {
        "goal_id": str(record.goal_id),
        "description": record.description,
        "kind": record.kind.value,
        "space_id": record.space_id,
        "health": health.value,
        "pipeline_stage": record.pipeline_stage,
        "archived": record.archived,
        "root_process_id": (
            str(record.root_process_id)
            if record.root_process_id is not None
            else None
        ),
        "process_ids": sorted(record.all_process_ids),
        "knowledge": knowledge,
        "stats": {
            "uptime_seconds": round(stats.uptime_seconds, 2),
            "active_child_count": stats.active_child_count,
            "knowledge_size_bytes": stats.knowledge_size_bytes,
            "last_event_at": (
                stats.last_event_at.isoformat()
                if stats.last_event_at is not None
                else None
            ),
        },
    }

  def _require(self, goal_id: GoalID) -> GoalRecord:
    record = self.get(goal_id)
    if record is None:
      raise GoalNotRegisteredError(f"Goal '{goal_id}' is not registered.")
    return record

  def _touch(self, record: GoalRecord) -> None:
    record.last_event_at = datetime.now(UTC)

  def _set_health_if_changed(
      self,
      record: GoalRecord,
      new_health: GoalHealth,
  ) -> None:
    previous = self._last_health.get(str(record.goal_id))
    if previous == new_health:
      return
    self._last_health[str(record.goal_id)] = new_health
    self._event_bus.publish(
        Event(
            event_type=EventType.GOAL_HEALTH_CHANGED,
            payload={
                "goal_id": str(record.goal_id),
                "health": new_health.value,
                "previous_health": previous.value if previous else None,
            },
        )
    )

  def _subscribe(self) -> None:
    for event_type in (
        EventType.PROCESS_CREATED,
        EventType.PROCESS_STARTED,
        EventType.PROCESS_COMPLETED,
        EventType.PROCESS_FAILED,
        EventType.GOAL_CREATED,
        EventType.GOAL_COMPLETED,
        EventType.GOAL_FAILED,
        EventType.STATE_CHANGED,
        EventType.USER_APPROVAL_REQUESTED,
        EventType.MEMORY_STORED,
    ):
      self._event_bus.subscribe(event_type, self._on_event)

  def _on_event(self, event: Event) -> None:
    if event.event_type == EventType.GOAL_CREATED:
      goal_id = str(event.payload.get("goal_id", ""))
      if goal_id and goal_id not in self._records:
        self.register(
            GoalID.from_string(goal_id),
            str(event.payload.get("description", "")),
        )
      return

    if event.event_type == EventType.GOAL_COMPLETED:
      goal_id = str(event.payload.get("goal_id", ""))
      record = self._records.get(goal_id)
      if record is None:
        return
      record.pipeline_stage = "completed"
      if record.kind == GoalKind.ONE_SHOT:
        record.archived = True
      self._touch(record)
      self._set_health_if_changed(record, self.compute_health(record))
      return

    if event.event_type == EventType.GOAL_FAILED:
      goal_id = str(event.payload.get("goal_id", ""))
      record = self._records.get(goal_id)
      if record is None:
        return
      record.has_process_failure = True
      record.pipeline_stage = "failed"
      self._touch(record)
      self._set_health_if_changed(record, GoalHealth.DEGRADED)
      return

    if event.event_type == EventType.STATE_CHANGED:
      key = str(getattr(event, "key", "") or event.payload.get("key", ""))
      if key == "pipeline_status":
        value = getattr(event, "new_value", None)
        if value is None:
          value = event.payload.get("new_value")
        for record in self._records.values():
          if not record.archived:
            record.pipeline_stage = str(value) if value is not None else None
            self._touch(record)
      return

    if event.event_type == EventType.USER_APPROVAL_REQUESTED:
      source = event.source_process
      if source is None:
        return
      goal_id = self._process_to_goal.get(str(source))
      if goal_id is None:
        return
      record = self._records.get(goal_id)
      if record is None:
        return
      record.pipeline_stage = "awaiting_approval"
      self._touch(record)
      self._set_health_if_changed(record, self.compute_health(record))
      return

    if event.event_type == EventType.MEMORY_STORED:
      source = event.source_process
      if source is None:
        return
      goal_id = self._process_to_goal.get(str(source))
      if goal_id is None:
        return
      record = self._records.get(goal_id)
      if record is not None:
        self._touch(record)
      return

    if event.event_type in {
        EventType.PROCESS_CREATED,
        EventType.PROCESS_STARTED,
        EventType.PROCESS_COMPLETED,
    }:
      source = event.source_process
      if source is None:
        return
      goal_id = self._process_to_goal.get(str(source))
      if goal_id is None:
        return
      record = self._records.get(goal_id)
      if record is None:
        return
      self._touch(record)
      self._set_health_if_changed(record, self.compute_health(record))
      self._publish_stats(record)
      return

    if event.event_type == EventType.PROCESS_FAILED:
      source = event.source_process
      if source is None:
        return
      goal_id = self._process_to_goal.get(str(source))
      if goal_id is None:
        return
      record = self._records.get(goal_id)
      if record is None:
        return
      record.has_process_failure = True
      error = str(event.payload.get("error", ""))
      if "budget" in error.lower():
        record.has_budget_exceeded = True
      self._touch(record)
      self._set_health_if_changed(record, GoalHealth.DEGRADED)
      self._publish_stats(record)

  def _publish_stats(self, record: GoalRecord) -> None:
    stats = self.compute_stats(record)
    self._event_bus.publish(
        Event(
            event_type=EventType.GOAL_STATS_UPDATED,
            payload={
                "goal_id": str(record.goal_id),
                "uptime_seconds": round(stats.uptime_seconds, 2),
                "active_child_count": stats.active_child_count,
                "knowledge_size_bytes": stats.knowledge_size_bytes,
                "last_event_at": (
                    stats.last_event_at.isoformat()
                    if stats.last_event_at is not None
                    else None
                ),
            },
        )
    )


def _pending_approvals_for_goal(
    record: GoalRecord,
    ctx: KernelContext,
) -> list[dict[str, Any]]:
  granted = {
      key.removeprefix("approval:")
      for key in ctx.state.keys()
      if key.startswith("approval:") and ctx.state.get(key)
  }

  pending: list[dict[str, Any]] = []
  for event in ctx.event_store.query(
      event_type=EventType.USER_APPROVAL_REQUESTED,
  ):
    source = event.source_process
    if source is None:
      continue
    if str(source) not in record.all_process_ids:
      continue
    request_id = str(event.payload.get("request_id", ""))
    if not request_id or request_id in granted:
      continue
    pending.append(
        {
            "request_id": request_id,
            "timestamp": event.timestamp,
        }
    )
  return pending
