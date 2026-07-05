from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """
    Declarative metadata for an installable process plugin.

    Loaded from plugin.yaml in each plugin directory.
    """

    name: str
    version: str
    description: str
    entrypoint: str
    runner: str = "python"
    required_capabilities: frozenset[str] = field(default_factory=frozenset)
    supported_events: frozenset[str] = field(default_factory=frozenset)
    config: dict[str, Any] = field(default_factory=dict)
    max_execution_time_seconds: int = 300

    @property
    def plugin_dir(self) -> Path | None:
        return self.config.get("_plugin_dir")

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("PluginManifest.name cannot be empty.")
        if not self.entrypoint.strip():
            raise ValueError("PluginManifest.entrypoint cannot be empty.")
