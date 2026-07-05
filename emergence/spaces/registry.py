from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


DEFAULT_SPACE_ID = "default"


@dataclass(slots=True)
class Space:
    """A namespace for goals, memory, and knowledge."""

    space_id: str
    name: str
    is_default: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SpaceRegistry:
    """Registry of user spaces with an active context."""

    def __init__(self) -> None:
        self._spaces: dict[str, Space] = {
            DEFAULT_SPACE_ID: Space(
                space_id=DEFAULT_SPACE_ID,
                name="Default",
                is_default=True,
            )
        }
        self._active_space_id = DEFAULT_SPACE_ID

    @property
    def active_space_id(self) -> str:
        return self._active_space_id

    def create(self, name: str) -> Space:
        space_id = str(uuid4())
        space = Space(space_id=space_id, name=name)
        self._spaces[space_id] = space
        return space

    def get(self, space_id: str) -> Space | None:
        return self._spaces.get(space_id)

    def list_all(self) -> list[Space]:
        return list(self._spaces.values())

    def list_views(self) -> list[dict[str, Any]]:
        return [
            {
                "space_id": space.space_id,
                "name": space.name,
                "is_default": space.is_default,
                "created_at": space.created_at.isoformat(),
            }
            for space in self._spaces.values()
        ]

    def switch(self, space_id: str) -> Space:
        space = self.get(space_id)
        if space is None:
            raise KeyError(space_id)
        self._active_space_id = space_id
        return space

    def desktop(self, ctx) -> dict[str, Any]:
        """Aggregate view for the active space desktop."""
        space_id = self._active_space_id
        goals = [
            view
            for view in ctx.goal_registry.list_views()
            if view.get("space_id", DEFAULT_SPACE_ID) == space_id
        ]
        attention = [
            goal for goal in goals if goal.get("health") in {"degraded", "needs_attention"}
        ]
        artifacts = ctx.knowledge_index.query(space_id=space_id)
        return {
            "space_id": space_id,
            "active_goals": len([g for g in goals if not g.get("archived")]),
            "attention_needed": len(attention),
            "recent_knowledge_count": len(artifacts),
            "goals": goals[:10],
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "active_space_id": self._active_space_id,
            "spaces": [
                {
                    "space_id": space.space_id,
                    "name": space.name,
                    "is_default": space.is_default,
                    "created_at": space.created_at.isoformat(),
                }
                for space in self._spaces.values()
            ],
        }

    def restore(self, data: dict[str, Any]) -> None:
        self._spaces.clear()
        for raw in data.get("spaces", []):
            space = Space(
                space_id=str(raw["space_id"]),
                name=str(raw["name"]),
                is_default=bool(raw.get("is_default", False)),
                created_at=datetime.fromisoformat(str(raw["created_at"])),
            )
            self._spaces[space.space_id] = space
        if not self._spaces:
            self._spaces[DEFAULT_SPACE_ID] = Space(
                space_id=DEFAULT_SPACE_ID,
                name="Default",
                is_default=True,
            )
        self._active_space_id = str(
            data.get("active_space_id", DEFAULT_SPACE_ID)
        )
        if self._active_space_id not in self._spaces:
            self._active_space_id = DEFAULT_SPACE_ID
