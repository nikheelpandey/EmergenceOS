"""Tests for emergence.memory.memory_manager — M5."""

from __future__ import annotations

import pytest

from emergence.core.event import EventType
from emergence.core.ids import ProcessID
from emergence.events.event_bus import EventBus
from emergence.memory.memory_category import MemoryCategory
from emergence.memory.memory_manager import MemoryManager
from emergence.memory.memory_store import MemoryStore
from emergence.security.capabilities import MEMORY_READ, MEMORY_WRITE
from emergence.security.errors import PermissionDeniedError
from emergence.security.gated_memory_manager import GatedMemoryManager
from emergence.security.security_manager import SecurityManager
from emergence.security.capability_manager import CapabilityManager


class TestMemoryManager:
    def test_store_and_retrieve_emits_events(self):
        bus = EventBus()
        events = []
        bus.subscribe(EventType.MEMORY_STORED, lambda e: events.append(e))
        bus.subscribe(EventType.MEMORY_RETRIEVED, lambda e: events.append(e))

        mgr = MemoryManager(MemoryStore(), bus)
        pid = ProcessID.new()

        mgr.store(pid, "note", "hello", category=MemoryCategory.WORKING)
        value = mgr.retrieve(pid, "note", category=MemoryCategory.WORKING)

        assert value == "hello"
        assert len(events) == 2
        assert events[0].event_type == EventType.MEMORY_STORED

    def test_gated_memory_denies_without_capability(self):
        bus = EventBus()
        mgr = MemoryManager(MemoryStore(), bus)
        caps = CapabilityManager()
        security = SecurityManager(caps)
        pid = ProcessID.new()

        gated = GatedMemoryManager(mgr, security, pid)

        with pytest.raises(PermissionDeniedError):
            gated.store("key", "value")

    def test_gated_memory_allows_with_capability(self):
        bus = EventBus()
        mgr = MemoryManager(MemoryStore(), bus)
        caps = CapabilityManager()
        security = SecurityManager(caps)
        pid = ProcessID.new()
        caps.grant(str(pid), MEMORY_READ)
        caps.grant(str(pid), MEMORY_WRITE)

        gated = GatedMemoryManager(mgr, security, pid)
        gated.store("key", "value", category=MemoryCategory.SEMANTIC)
        assert gated.retrieve("key", category=MemoryCategory.SEMANTIC) == "value"
