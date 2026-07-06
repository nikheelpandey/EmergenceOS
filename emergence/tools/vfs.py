from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from emergence.persistence.paths import ensure_data_dir


class VirtualFilesystem:
    """Capability-gated virtual filesystem under the data directory."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or (ensure_data_dir() / "vfs")

    def _resolve(self, space_id: str, path: str) -> Path:
        normalized = path.strip().replace("\\", "/").lstrip("/")
        if not normalized:
            normalized = "."
        parts = Path(normalized).parts
        if ".." in parts:
            raise ValueError("path traversal is not allowed")
        target = (self._root / space_id / normalized).resolve()
        space_root = (self._root / space_id).resolve()
        if not str(target).startswith(str(space_root)):
            raise ValueError("path escapes space root")
        return target

    def read(self, space_id: str, path: str, *, encoding: str = "utf-8") -> dict[str, Any]:
        target = self._resolve(space_id, path)
        if not target.exists():
            raise FileNotFoundError(path)
        if target.is_dir():
            raise IsADirectoryError(path)
        data = target.read_bytes()
        try:
            content = data.decode(encoding)
            binary = False
        except UnicodeDecodeError:
            content = data.decode("latin-1")
            binary = True
        stat = target.stat()
        return {
            "path": path,
            "content": content,
            "binary": binary,
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
        }

    def write(
        self,
        space_id: str,
        path: str,
        content: str,
        *,
        encoding: str = "utf-8",
        mkdirs: bool = True,
    ) -> dict[str, Any]:
        target = self._resolve(space_id, path)
        if mkdirs:
            target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.is_dir():
            raise IsADirectoryError(path)
        target.write_text(content, encoding=encoding)
        stat = target.stat()
        return {
            "path": path,
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
        }

    def list(self, space_id: str, path: str = ".") -> dict[str, Any]:
        target = self._resolve(space_id, path)
        if not target.exists():
            raise FileNotFoundError(path)
        if not target.is_dir():
            raise NotADirectoryError(path)
        entries = []
        for child in sorted(target.iterdir()):
            stat = child.stat()
            entries.append(
                {
                    "name": child.name,
                    "path": str(child.relative_to(self._root / space_id)),
                    "is_dir": child.is_dir(),
                    "size_bytes": stat.st_size if child.is_file() else 0,
                    "modified_at": stat.st_mtime,
                }
            )
        return {"path": path, "entries": entries}

    def delete(self, space_id: str, path: str) -> dict[str, Any]:
        target = self._resolve(space_id, path)
        if not target.exists():
            raise FileNotFoundError(path)
        if target.is_dir():
            if any(target.iterdir()):
                raise OSError("directory not empty")
            target.rmdir()
        else:
            target.unlink()
        return {"path": path, "deleted": True}

    def stat(self, space_id: str, path: str) -> dict[str, Any]:
        target = self._resolve(space_id, path)
        if not target.exists():
            raise FileNotFoundError(path)
        stat = target.stat()
        return {
            "path": path,
            "is_dir": target.is_dir(),
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
        }
