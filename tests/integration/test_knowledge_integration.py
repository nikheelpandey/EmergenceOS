"""Integration tests for Knowledge Layer (M22)."""

from __future__ import annotations

import pytest

from emergence.admin.client import AdminClient
from emergence.core.process_definition import ProcessDefinition
from emergence.kernel.boot_context import build_research_assistant, create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.kernel.runtime import RuntimeService
from emergence.memory.memory_category import MemoryCategory
from emergence.persistence.flush import flush_persistence
from emergence.persistence.paths import knowledge_path
from tests.helpers_admin import short_data_dir


@pytest.mark.integration
class TestKnowledgeIntegration:
    def test_research_assistant_populates_knowledge_index(self):
        kernel, goal = build_research_assistant("quantum computing")
        kernel.run()

        artifacts = kernel.context.knowledge_index.query(goal_id=goal.goal_id)
        types = {item["artifact_type"] for item in artifacts}

        assert len(artifacts) >= 2
        assert "finding" in types
        assert "report" in types

        summary = kernel.context.knowledge_index.summarize_goal(goal.goal_id)
        assert summary["artifact_count"] == len(artifacts)
        assert "reports" in summary["display"]
        assert "findings" in summary["display"]

    def test_knowledge_survives_restart(self, monkeypatch):
        data_dir = short_data_dir("knowledge-persist")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        ctx1 = create_kernel_context(persist=True)
        kernel1 = Kernel(
            ctx=ctx1,
            executor=ctx1.executor,
            lifecycle=LifecycleManager(),
        )
        goal = kernel1.create_goal("Persistent knowledge")
        definition = ProcessDefinition(
            name="researcher",
            implementation="researcher",
            version="1.0.0",
        )
        process = kernel1.spawn(definition, goal_id=goal.goal_id)
        ctx1.memory.store(
            process.process_id,
            "findings",
            "durable finding",
            category=MemoryCategory.EPISODIC,
        )
        flush_persistence(ctx1)
        ctx1.checkpoints.close()

        assert knowledge_path().exists()

        ctx2 = create_kernel_context(persist=True)
        try:
            artifacts = ctx2.knowledge_index.query(goal_id=goal.goal_id)
            assert len(artifacts) == 1
            assert artifacts[0]["artifact_type"] == "finding"
        finally:
            ctx2.checkpoints.close()

    def test_admin_knowledge_list(self, monkeypatch):
        data_dir = short_data_dir("knowledge-admin")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        from emergence.admin.client import AdminClient
        from emergence.kernel.runtime import RuntimeService

        service = RuntimeService.start()
        try:
            goal = service.kernel.create_goal("Admin knowledge goal")
            definition = service.kernel.context.registry.get("job_worker")
            process = service.kernel.spawn(definition, goal_id=goal.goal_id)
            service.kernel.context.memory.store(
                process.process_id,
                "report",
                "# Final report",
                category=MemoryCategory.SEMANTIC,
            )

            client = AdminClient.connect()
            payload = client.call(
                "knowledge.list",
                params={"goal_id": str(goal.goal_id)},
            )
            assert len(payload["artifacts"]) == 1
            assert payload["summary"]["artifact_count"] == 1

            artifact_id = payload["artifacts"][0]["artifact_id"]
            detail = client.call(
                "knowledge.get",
                params={"artifact_id": artifact_id},
            )
            assert detail["artifact_type"] == "report"
            assert detail["provenance"]["event_id"] == artifact_id
        finally:
            service.stop()
