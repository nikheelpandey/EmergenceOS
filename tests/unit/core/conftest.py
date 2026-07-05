"""
Fixtures for emergence.core unit tests.
"""

from __future__ import annotations

import pytest

from emergence.events.event_bus import EventBus
from emergence.kernel.mailbox_manager import MailboxManager
from emergence.kernel.state_store import StateStore


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def state_store(event_bus: EventBus) -> StateStore:
    return StateStore(event_bus)


@pytest.fixture
def mailbox_manager(event_bus: EventBus) -> MailboxManager:
    return MailboxManager(event_bus)
