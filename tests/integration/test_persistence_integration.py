"""
Unit tests for durable persistence (M20).
"""

from __future__ import annotations

import json

import pytest

from emergence.checkpoint.checkpoint import Checkpoint
from emergence.checkpoint.sqlite_adapter import SQLiteCheckpointStore
from emergence.core.ids import ProcessID
from emergence.core.state import ProcessState
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.memory.file_memory_store import FileMemoryStore
from emergence.memory.memory_category import MemoryCategory
from emergence.persistence.flush import flush_persistence, restore_persistence
from emergence.persistence.paths import (
    cognitive_path,
    events_path,
    memory_path,
    state_path,
)
from tests.helpers_admin import short_data_dir


@pytest.mark.unit
class TestFileMemoryStore:
    def test_persists_to_disk(self, monkeypatch):
        data_dir = short_data_dir("memory")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        store = FileMemoryStore(memory_path())
        store.set("semantic:pid:note", "hello")

        reloaded = FileMemoryStore(memory_path())
        assert reloaded.get("semantic:pid:note") == "hello"


@pytest.mark.unit
class TestSQLiteCheckpointStore:
    def test_save_and_load_latest(self, tmp_path):
        db = tmp_path / "checkpoints.db"
        store = SQLiteCheckpointStore(db)
        checkpoint = Checkpoint(
            process_id=ProcessID.new(),
            process_state=ProcessState.WAITING,
            working_memory={"stage": 2},
        )
        store.save(checkpoint)

        latest = store.latest_for_process(str(checkpoint.process_id))
        assert latest is not None
        assert latest.working_memory["stage"] == 2


@pytest.mark.integration
class TestPersistenceIntegration:
    def test_goal_and_state_survive_restart(self, monkeypatch):
        data_dir = short_data_dir("persist")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        ctx1 = create_kernel_context(persist=True)
        kernel1 = Kernel(
            ctx=ctx1,
            executor=ctx1.executor,
            lifecycle=LifecycleManager(),
        )
        goal = kernel1.create_goal("Research event-driven architecture")
        ctx1.state.set("research_topic", "event-driven architecture")
        ctx1.memory.store(
            ProcessID.new(),
            "finding",
            "events are immutable",
            category=MemoryCategory.SEMANTIC,
        )
        flush_persistence(ctx1)
        ctx1.checkpoints.close()

        assert events_path().exists()
        assert memory_path().exists()
        assert state_path().exists()
        assert cognitive_path().exists()

        ctx2 = create_kernel_context(persist=True)
        try:
            assert ctx2.state.get("research_topic") == "event-driven architecture"
            assert len(ctx2.cognitive.snapshot()["goals"]) == 1
            assert ctx2.cognitive.snapshot()["goals"][0]["description"] == (
                "Research event-driven architecture"
            )
            assert events_path().exists()
            assert json.loads(memory_path().read_text())
        finally:
            ctx2.checkpoints.close()

    def test_runtime_service_flushes_on_stop(self, monkeypatch):
        data_dir = short_data_dir("runtime-persist")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        from emergence.kernel.runtime import RuntimeService

        service = RuntimeService.start()
        service.kernel.create_goal("Persistent workload")
        service.stop()

        cognitive = json.loads(cognitive_path().read_text())
        assert len(cognitive["goals"]) == 1
