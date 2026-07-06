"""Integration tests for ArtifactService persistence and tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from emergence.core.ids import ProcessID
from emergence.core.process_definition import ProcessDefinition
from emergence.executor.tool_model import ToolRequest
from emergence.kernel.boot_context import build_kernel
from emergence.persistence.flush import flush_persistence
from emergence.security.capabilities import ARTIFACT_READ, ARTIFACT_WRITE


@pytest.mark.integration
class TestArtifactIntegration:
    def test_persistence_survives_restart(self, tmp_path: Path, monkeypatch):
        data_dir = tmp_path / "runtime"
        data_dir.mkdir()
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))
        monkeypatch.setenv("EMERGENCE_PERSIST", "1")

        kernel = build_kernel(spawn=None, load_plugins=False, persist=True)
        ctx = kernel.context
        process_id = ProcessID.new()

        record = ctx.artifact_service.create(
            name="OfferComparison.xlsx",
            artifact_type="spreadsheet",
            content="company,offer\nGoogle,500k",
            owner_process_id=process_id,
            tags=["offers"],
        )
        flush_persistence(ctx)

        kernel2 = build_kernel(spawn=None, load_plugins=False, persist=True)
        restored = kernel2.context.artifact_service.get(record.artifact_id)
        assert restored is not None
        assert restored.name == "OfferComparison.xlsx"
        content = kernel2.context.artifact_service.read_content(record.artifact_id)
        assert content == b"company,offer\nGoogle,500k"

    def test_artifact_tools_round_trip(self, tmp_path: Path, monkeypatch):
        data_dir = tmp_path / "runtime"
        data_dir.mkdir()
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        kernel = build_kernel(spawn=None, load_plugins=False)
        ctx = kernel.context

        definition = ProcessDefinition(
            name="artifact_worker",
            implementation="artifact_worker",
            version="1.0.0",
            required_permissions=frozenset({"artifact.read", "artifact.write"}),
        )
        ctx.registry.register(definition)
        process = kernel.spawn(definition)
        pid = process.process_id

        ctx.capabilities.grant(str(pid), ARTIFACT_READ)
        ctx.capabilities.grant(str(pid), ARTIFACT_WRITE)

        create_result = ctx.tools.execute(
            ToolRequest(tool_name="artifact.create", arguments={
                "name": "ArchitectureDiagram.png",
                "type": "image",
                "content": "png-binary-placeholder",
                "tags": ["portfolio"],
            }),
            pid,
        )
        assert create_result.success
        artifact_id = create_result.result["artifact_id"]

        search_result = ctx.tools.execute(
            ToolRequest(tool_name="artifact.search", arguments={
                "type": "image",
                "query": "architecture",
            }),
            pid,
        )
        assert search_result.success
        assert search_result.result["count"] == 1

        update_result = ctx.tools.execute(
            ToolRequest(tool_name="artifact.update", arguments={
                "artifact_id": artifact_id,
                "content": "updated diagram",
            }),
            pid,
        )
        assert update_result.success
        assert update_result.result["version"] == 2

        export_result = ctx.tools.execute(
            ToolRequest(tool_name="artifact.export", arguments={
                "artifact_id": artifact_id,
            }),
            pid,
        )
        assert export_result.success
        assert export_result.result == "updated diagram"
