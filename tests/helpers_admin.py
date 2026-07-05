"""Shared helpers for admin tests."""

from __future__ import annotations

import os
import uuid
from pathlib import Path


def short_data_dir(name: str = "data") -> Path:
    """
    Return a short data directory for EMERGENCE_DATA_DIR in tests.

    Uses a workspace-local path so Unix socket bind works in the sandbox
    and stays under the macOS 104-byte AF_UNIX limit.
    """
    path = (
        Path.cwd()
        / ".test-runtime"
        / f"{os.getpid()}-{uuid.uuid4().hex[:8]}-{name}"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path
