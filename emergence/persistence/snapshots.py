from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from emergence.artifacts.service import ArtifactService
from emergence.cognitive.goal_registry import GoalRegistry
from emergence.cognitive.manager import CognitiveManager
from emergence.memory.knowledge_index import KnowledgeIndex
from emergence.core.goal import Goal
from emergence.core.ids import GoalID, PlanID, TaskID
from emergence.core.plan import Plan
from emergence.core.state import GoalState, PlanState, TaskState
from emergence.core.task import Task
from emergence.kernel.state_store import StateStore


def save_state_snapshot(state: StateStore, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state.snapshot(), indent=2, default=str) + "\n"
    )


def load_state_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data if isinstance(data, dict) else {}


def restore_state_snapshot(state: StateStore, path: Path) -> None:
    snapshot = load_state_snapshot(path)
    for key, value in snapshot.items():
        state.set(key, value)


def save_goal_registry_snapshot(registry: GoalRegistry, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(registry.snapshot(), indent=2, default=str) + "\n"
    )


def restore_goal_registry_snapshot(
    registry: GoalRegistry,
    path: Path,
) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text())
    registry.restore(data)


def save_knowledge_snapshot(index: KnowledgeIndex, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(index.snapshot(), indent=2, default=str) + "\n"
    )


def restore_knowledge_snapshot(index: KnowledgeIndex, path: Path) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text())
    index.restore(data)


def save_artifacts_snapshot(service: ArtifactService, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(service.snapshot(), indent=2, default=str) + "\n"
    )


def restore_artifacts_snapshot(service: ArtifactService, path: Path) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text())
    service.restore(data)


def save_spaces_snapshot(registry, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(registry.snapshot(), indent=2, default=str) + "\n"
    )


def restore_spaces_snapshot(registry, path: Path) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text())
    registry.restore(data)


def save_schedules_snapshot(manager, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manager.snapshot(), indent=2, default=str) + "\n"
    )


def restore_schedules_snapshot(manager, path: Path) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text())
    manager.restore(data)


def save_cognitive_snapshot(cognitive: CognitiveManager, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cognitive.snapshot(), indent=2, default=str) + "\n"
    )


def restore_cognitive_snapshot(
    cognitive: CognitiveManager,
    path: Path,
) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text())
    cognitive.restore(data)


def cognitive_to_dict(cognitive: CognitiveManager) -> dict[str, Any]:
    return cognitive.snapshot()
