from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from emergence.plugins.manifest import PluginManifest

_LIST_ITEM = re.compile(r"^\s+-\s+(.+)$")


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """
    Parse a minimal YAML subset: scalars and dash-lists only.

    Sufficient for plugin.yaml manifests without external deps.
    """
    result: dict[str, Any] = {}
    current_key: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        list_match = _LIST_ITEM.match(line)
        if list_match and current_key is not None:
            result.setdefault(current_key, [])
            result[current_key].append(_parse_scalar(list_match.group(1)))
            continue

        if ":" not in stripped:
            continue

        key, _, raw_value = stripped.partition(":")
        key = key.strip()
        value = raw_value.strip()

        if value:
            result[key] = _parse_scalar(value)
            current_key = None
        else:
            result[key] = []
            current_key = key

    return result


def _parse_scalar(value: str) -> Any:
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def load_manifest(path: Path) -> PluginManifest:
    """Load a PluginManifest from a plugin.yaml file."""
    data = parse_simple_yaml(path.read_text(encoding="utf-8"))

    caps = data.get("required_capabilities", [])
    events = data.get("supported_events", [])

    manifest = PluginManifest(
        name=str(data["name"]),
        version=str(data.get("version", "1.0.0")),
        description=str(data.get("description", "")),
        entrypoint=str(data["entrypoint"]),
        runner=str(data.get("runner", "python")),
        required_capabilities=frozenset(str(c) for c in caps),
        supported_events=frozenset(str(e) for e in events),
        config=dict(data.get("config", {})),
        max_execution_time_seconds=int(
            data.get("max_execution_time_seconds", 300)
        ),
    )
    object.__setattr__(
        manifest,
        "config",
        {**manifest.config, "_plugin_dir": path.parent},
    )
    return manifest


def discover_plugin_dirs(plugins_root: Path) -> list[Path]:
    """Return plugin directories containing a plugin.yaml manifest."""
    if not plugins_root.is_dir():
        return []

    dirs: list[Path] = []
    for child in sorted(plugins_root.iterdir()):
        if child.is_dir() and (child / "plugin.yaml").exists():
            dirs.append(child)
    return dirs
