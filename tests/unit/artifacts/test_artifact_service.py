"""Unit tests for ArtifactService."""

from __future__ import annotations

from pathlib import Path

import pytest

from emergence.core.event import EventType
from emergence.core.ids import GoalID, ProcessID
from emergence.core.process import Process
from emergence.core.process_definition import ProcessDefinition
from emergence.kernel.boot_context import create_kernel_context
from emergence.artifacts.service import ArtifactStatus, create_artifact_service


@pytest.fixture
def artifact_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))
    return data_dir


@pytest.mark.unit
class TestArtifactService:
    def test_create_emits_event_and_indexes_by_goal(self, artifact_data_dir: Path):
        ctx = create_kernel_context()
        service = ctx.artifact_service
        goal_id = GoalID.new()
        process_id = ProcessID.new()

        ctx.goal_registry.register(goal_id, "Land Principal AI Role")
        ctx.goal_registry.associate_process(goal_id, process_id)
        definition = ProcessDefinition(
            name="resume_generator",
            implementation="resume_generator",
            version="1.0.0",
        )
        ctx.process_table.add(Process(definition=definition, process_id=process_id))

        record = service.create(
            name="Resume.pdf",
            artifact_type="resume",
            content="Principal AI engineer resume body",
            owner_process_id=process_id,
            tags=["google", "principal"],
        )

        assert record.version == 1
        assert record.status == ArtifactStatus.ACTIVE
        assert record.owner_goal_id == goal_id

        results = service.search(artifact_type="resume", goal_id=goal_id)
        assert len(results) == 1
        assert results[0]["name"] == "Resume.pdf"
        assert "google" in results[0]["tags"]

        events = [
            event
            for event in ctx.event_store.query()
            if event.event_type == EventType.ARTIFACT_CREATED
        ]
        assert len(events) == 1
        assert events[0].payload["artifact_type"] == "resume"

    def test_update_creates_new_version_and_supersedes_old(self, artifact_data_dir: Path):
        ctx = create_kernel_context()
        service = ctx.artifact_service
        process_id = ProcessID.new()

        original = service.create(
            name="Resume.pdf",
            artifact_type="resume",
            content="version 7",
            owner_process_id=process_id,
        )
        updated = service.update(
            original.artifact_id,
            content="version 8",
            owner_process_id=process_id,
        )

        assert updated.version == 2
        assert updated.lineage_id == original.lineage_id
        assert service.get(original.artifact_id).status == ArtifactStatus.SUPERSEDED

        latest = service.search(artifact_type="resume", query="resume")
        assert len(latest) == 1
        assert latest[0]["version"] == 2

        update_events = [
            event
            for event in ctx.event_store.query()
            if event.event_type == EventType.ARTIFACT_UPDATED
        ]
        assert len(update_events) == 1

    def test_search_by_query_and_tags(self, artifact_data_dir: Path):
        ctx = create_kernel_context()
        service = ctx.artifact_service
        process_id = ProcessID.new()

        service.create(
            name="Resume_Google.pdf",
            artifact_type="resume",
            content="tailored for Google",
            owner_process_id=process_id,
            tags=["google"],
        )
        service.create(
            name="InterviewNotes_Anthropic.md",
            artifact_type="notes",
            content="system design discussion",
            owner_process_id=process_id,
            tags=["anthropic", "interview"],
        )

        google_resumes = service.search(query="google", artifact_type="resume")
        assert len(google_resumes) == 1
        assert google_resumes[0]["name"] == "Resume_Google.pdf"

        anthropic_notes = service.search(query="anthropic")
        assert len(anthropic_notes) == 1
        assert anthropic_notes[0]["artifact_type"] == "notes"

    def test_link_and_provenance(self, artifact_data_dir: Path):
        ctx = create_kernel_context()
        service = ctx.artifact_service
        process_id = ProcessID.new()

        base = service.create(
            name="Resume.pdf",
            artifact_type="resume",
            content="base resume",
            owner_process_id=process_id,
        )
        tailored = service.create(
            name="Resume_OpenAI.pdf",
            artifact_type="resume",
            content="tailored resume",
            owner_process_id=process_id,
            based_on=base.artifact_id,
            provenance={"prompt": "Tailor for OpenAI principal role"},
        )

        assert tailored.provenance["based_on_artifact_id"] == str(base.artifact_id)
        assert tailored.provenance["prompt"] == "Tailor for OpenAI principal role"

        service.link(tailored.artifact_id, str(base.artifact_id), link_type="derived_from")
        view = service.search(artifact_type="resume", query="OpenAI")[0]
        assert str(base.artifact_id) in view["links"]["derived_from"]

    def test_watch_registers_notification(self, artifact_data_dir: Path):
        bus = create_kernel_context().event_bus
        service = create_artifact_service(bus)
        process_id = ProcessID.new()

        service.register_watch(process_id, artifact_type="resume")
        service.create(
            name="Resume.pdf",
            artifact_type="resume",
            content="body",
            owner_process_id=process_id,
        )

        assert service.consume_notification(process_id) is True
        assert service.consume_notification(process_id) is False

    def test_snapshot_round_trip(self, artifact_data_dir: Path):
        ctx = create_kernel_context()
        service = ctx.artifact_service
        process_id = ProcessID.new()

        created = service.create(
            name="Portfolio.pdf",
            artifact_type="portfolio",
            content="portfolio content",
            owner_process_id=process_id,
        )

        snapshot = service.snapshot()
        service.restore({"artifacts": [], "watches": []})
        assert service.get(created.artifact_id) is None

        service.restore(snapshot)
        restored = service.get(created.artifact_id)
        assert restored is not None
        assert restored.name == "Portfolio.pdf"
        assert service.read_content(created.artifact_id) == b"portfolio content"
