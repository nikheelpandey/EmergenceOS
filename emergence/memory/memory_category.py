from __future__ import annotations

from enum import Enum


class MemoryCategory(str, Enum):
    """Categories of long-term memory managed by the Memory Manager."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
