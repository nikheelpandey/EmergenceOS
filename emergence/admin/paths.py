from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


def data_dir() -> Path:
    """Return the EmergenceOS data directory."""
    override = os.environ.get("EMERGENCE_DATA_DIR")
    if override:
        return Path(override)
    return Path.home() / ".emergence"


def manifest_path() -> Path:
    return data_dir() / "runtime.json"


def pid_path() -> Path:
    return data_dir() / "runtime.pid"


@dataclass(frozen=True, slots=True)
class RuntimeManifest:
    pid: int
    host: str
    port: int
    started_at: str
    http_port: int | None = None

    def to_dict(self) -> dict[str, object]:
        data = {
            "pid": self.pid,
            "host": self.host,
            "port": self.port,
            "started_at": self.started_at,
        }
        if self.http_port is not None:
            data["http_port"] = self.http_port
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> RuntimeManifest:
        http_port = data.get("http_port")
        return cls(
            pid=int(data["pid"]),  # type: ignore[arg-type]
            host=str(data["host"]),
            port=int(data["port"]),  # type: ignore[arg-type]
            started_at=str(data["started_at"]),
            http_port=int(http_port) if http_port is not None else None,  # type: ignore[arg-type]
        )


def write_manifest(manifest: RuntimeManifest) -> None:
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), indent=2) + "\n")


def read_manifest() -> RuntimeManifest | None:
    path = manifest_path()
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return RuntimeManifest.from_dict(data)
