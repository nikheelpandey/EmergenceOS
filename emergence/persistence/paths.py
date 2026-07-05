from __future__ import annotations

import os
from pathlib import Path

from emergence.admin.paths import data_dir


def should_persist() -> bool:
    """Return True when durable storage should be enabled."""
    flag = os.environ.get("EMERGENCE_PERSIST", "").lower()
    if flag in {"0", "false", "no"}:
        return False
    if flag in {"1", "true", "yes"}:
        return True
    return os.environ.get("EMERGENCE_DATA_DIR") is not None


def events_path() -> Path:
    return data_dir() / "events.jsonl"


def memory_path() -> Path:
    return data_dir() / "memory.json"


def checkpoints_path() -> Path:
    return data_dir() / "checkpoints.db"


def state_path() -> Path:
    return data_dir() / "state.json"


def goal_registry_path() -> Path:
    return data_dir() / "goal_registry.json"


def knowledge_path() -> Path:
    return data_dir() / "knowledge.json"


def cognitive_path() -> Path:
    return data_dir() / "cognitive.json"


def spaces_path() -> Path:
    return data_dir() / "spaces.json"


def schedules_path() -> Path:
    return data_dir() / "schedules.json"


def ensure_data_dir() -> Path:
    path = data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path
