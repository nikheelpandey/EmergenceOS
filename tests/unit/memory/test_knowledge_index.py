"""Unit tests for KnowledgeIndex (M22)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from emergence.core.ids import GoalID, ProcessID
from emergence.core.process import Process
from emergence.core.process_definition import ProcessDefinition
from emergence.events.memory_events import MemoryStoredEvent
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.memory.knowledge_index import (
    ArtifactType,
    KnowledgeIndex,
    create_knowledge_index,
    format_bytes,
    infer_artifact_type,
)
from emergence.memory.memory_category import MemoryCategory


@pytest.mark.unit
class TestKnowledgeHelpers:
    def test_infer_artifact_type(self):
        assert infer_artifact_type("report", MemoryCategory.SEMANTIC) == (
            ArtifactType.REPORT
        )
        assert infer_artifact_type("findings", MemoryCategory.EPISODIC) == (
            ArtifactType.FINDING
        )
        assert infer_artifact_type("notes", MemoryCategory.SEMANTIC) == (
            ArtifactType.DOCUMENT
        )

    def test_format_bytes(self):
        assert format_bytes(150 * 1024 * 1024) == "150 MB"
        assert format_bytes(2048) == "2 KB"


@pytest.mark.unit
class TestKnowledgeIndex:
    def test_indexes_memory_stored_event_for_goal(self):
        ctx = create_kernel_context()
        index = ctx.knowledge_index
        goal_id = GoalID.new()
        process_id = ProcessID.new()
        ctx.goal_registry.register(goal_id, "Research goal")
        ctx.goal_registry.associate_process(goal_id, process_id)

        definition = ProcessDefinition(
            name="research_assistant",
            implementation="research_assistant",
            version="1.0.0",
        )
        process = Process(definition=definition, process_id=process_id)
        ctx.process_table.add(process)

        ctx.event_bus.publish(
            MemoryStoredEvent(
                process_id=process_id,
                key="findings",
                category=MemoryCategory.EPISODIC,
                source_process=process_id,
                payload={"value": "Gandhi led the Salt March."},
            )
        )

        artifacts = index.query(goal_id=goal_id)
        assert len(artifacts) == 1
        assert artifacts[0]["artifact_type"] == "finding"
        assert artifacts[0]["provenance"]["plugin"] == "research_assistant"
        assert artifacts[0]["size_bytes"] > 0

    def test_query_filters_by_type(self):
        bus = create_kernel_context().event_bus
        index = create_knowledge_index(bus)
        goal_id = GoalID.new()
        process_id = ProcessID.new()

        for key, category, artifact_type in (
            ("findings", MemoryCategory.EPISODIC, ArtifactType.FINDING),
            ("report", MemoryCategory.SEMANTIC, ArtifactType.REPORT),
        ):
            event = MemoryStoredEvent(
                process_id=process_id,
                key=key,
                category=category,
                source_process=process_id,
                payload={"value": f"{key} body"},
            )
            bus.publish(event)
            stored = index.get(str(event.event_id))
            assert stored is not None
            object.__setattr__(stored, "goal_id", goal_id)
            index._by_goal[str(goal_id)].append(str(event.event_id))  # noqa: SLF001

        findings = index.query(
            goal_id=goal_id,
            artifact_type=ArtifactType.FINDING,
        )
        assert len(findings) == 1
        assert findings[0]["artifact_type"] == "finding"

    def test_summarize_goal_display(self):
        index = create_knowledge_index(create_kernel_context().event_bus)
        goal_id = GoalID.new()
        now = datetime.now(UTC)

        for idx in range(3):
            artifact_id = f"artifact-{idx}"
            from emergence.memory.knowledge_index import KnowledgeArtifact
            from emergence.core.ids import EventID

            index._artifacts[artifact_id] = KnowledgeArtifact(  # noqa: SLF001
                artifact_id=artifact_id,
                goal_id=goal_id,
                artifact_type=ArtifactType.DOCUMENT,
                key=f"doc-{idx}",
                category=MemoryCategory.SEMANTIC,
                process_id=ProcessID.new(),
                plugin="researcher",
                size_bytes=50 * 1024 * 1024,
                stored_at=now - timedelta(minutes=2),
                event_id=EventID.new(),
            )
            index._by_goal[str(goal_id)].append(artifact_id)  # noqa: SLF001

        report = KnowledgeArtifact(
            artifact_id="report-1",
            goal_id=goal_id,
            artifact_type=ArtifactType.REPORT,
            key="report",
            category=MemoryCategory.SEMANTIC,
            process_id=ProcessID.new(),
            plugin="research_assistant",
            size_bytes=1024,
            stored_at=now,
            event_id=EventID.new(),
        )
        index._artifacts["report-1"] = report  # noqa: SLF001
        index._by_goal[str(goal_id)].append("report-1")  # noqa: SLF001

        summary = index.summarize_goal(goal_id)
        assert "MB" in summary["display"]
        assert "3 docs" in summary["display"]
        assert "1 reports" in summary["display"]
        assert summary["artifact_count"] == 4

    def test_snapshot_round_trip(self):
        index = create_knowledge_index(create_kernel_context().event_bus)
        goal_id = GoalID.new()
        process_id = ProcessID.new()

        event = MemoryStoredEvent(
            process_id=process_id,
            key="findings",
            category=MemoryCategory.EPISODIC,
            source_process=process_id,
            payload={"value": "stored knowledge"},
        )
        index.event_bus.publish(event)
        stored = index.get(str(event.event_id))
        assert stored is not None
        object.__setattr__(stored, "goal_id", goal_id)
        index._by_goal[str(goal_id)].append(str(event.event_id))  # noqa: SLF001

        data = index.snapshot()
        restored = create_knowledge_index(create_kernel_context().event_bus)
        restored.restore(data)

        assert restored.get(str(event.event_id)) is not None

    def test_goal_registry_uses_knowledge_index_stats(self):
        ctx = create_kernel_context()
        kernel = Kernel(
            ctx=ctx,
            executor=ctx.executor,
            lifecycle=LifecycleManager(),
        )
        goal = kernel.create_goal("Knowledge goal")
        definition = ProcessDefinition(
            name="researcher",
            implementation="researcher",
            version="1.0.0",
        )
        process = kernel.spawn(definition, goal_id=goal.goal_id)
        ctx.memory.store(
            process.process_id,
            "findings",
            "important discovery",
            category=MemoryCategory.EPISODIC,
        )

        view = ctx.goal_registry.query(goal.goal_id)
        assert view is not None
        assert view["stats"]["knowledge_size_bytes"] > 0
        assert view["knowledge"]["artifact_count"] == 1
        assert "finding" in view["knowledge"]["counts_by_type"]
