"""
SQLite adapter for checkpoint persistence.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from emergence.checkpoint.checkpoint import Checkpoint
from emergence.checkpoint.checkpoint_store import CheckpointStore
from emergence.core.budget_tracker import BudgetUsage
from emergence.core.ids import ProcessID
from emergence.core.state import ProcessState


class SQLiteCheckpointStore(CheckpointStore):
    """SQLite-backed checkpoint store."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def save(self, checkpoint: Checkpoint) -> None:
        payload = _checkpoint_to_dict(checkpoint)
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO checkpoints
                (checkpoint_id, process_id, payload, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    checkpoint.checkpoint_id,
                    str(checkpoint.process_id),
                    json.dumps(payload, default=str),
                    checkpoint.created_at.isoformat(),
                ),
            )
            conn.commit()

    def get(self, checkpoint_id: str) -> Checkpoint | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT payload FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,),
            ).fetchone()
        if row is None:
            return None
        return _checkpoint_from_dict(json.loads(row[0]))

    def latest_for_process(self, process_id: str) -> Checkpoint | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT payload FROM checkpoints
                WHERE process_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (process_id,),
            ).fetchone()
        if row is None:
            return None
        return _checkpoint_from_dict(json.loads(row[0]))

    def list_for_process(self, process_id: str) -> list[Checkpoint]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT payload FROM checkpoints
                WHERE process_id = ?
                ORDER BY created_at ASC
                """,
                (process_id,),
            ).fetchall()
        return [_checkpoint_from_dict(json.loads(row[0])) for row in rows]

    def close(self) -> None:
        """No persistent connection — included for API compatibility."""

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    process_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()


def _checkpoint_to_dict(checkpoint: Checkpoint) -> dict[str, object]:
    return {
        "checkpoint_id": checkpoint.checkpoint_id,
        "process_id": str(checkpoint.process_id),
        "process_state": checkpoint.process_state.value,
        "working_memory": checkpoint.working_memory,
        "event_offset": checkpoint.event_offset,
        "resource_usage": asdict(checkpoint.resource_usage),
        "created_at": checkpoint.created_at.isoformat(),
    }


def _checkpoint_from_dict(data: dict[str, object]) -> Checkpoint:
    usage_raw = data.get("resource_usage") or {}
    usage = BudgetUsage(
        tokens=int(usage_raw.get("tokens", 0)),  # type: ignore[union-attr]
        tool_invocations=int(usage_raw.get("tool_invocations", 0)),  # type: ignore[union-attr]
        cost_usd=float(usage_raw.get("cost_usd", 0.0)),  # type: ignore[union-attr]
        execution_seconds=float(usage_raw.get("execution_seconds", 0.0)),  # type: ignore[union-attr]
        retries=int(usage_raw.get("retries", 0)),  # type: ignore[union-attr]
    )
    return Checkpoint(
        checkpoint_id=str(data["checkpoint_id"]),
        process_id=ProcessID(str(data["process_id"])),
        process_state=ProcessState(str(data["process_state"])),
        working_memory=dict(data.get("working_memory", {})),  # type: ignore[arg-type]
        event_offset=int(data.get("event_offset", 0)),  # type: ignore[arg-type]
        resource_usage=usage,
        created_at=datetime.fromisoformat(str(data["created_at"])),
    )
