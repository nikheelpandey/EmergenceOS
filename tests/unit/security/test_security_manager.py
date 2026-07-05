"""
Tests for emergence.security — capability enforcement.
"""

from __future__ import annotations

import pytest

from emergence.common.message import Message
from emergence.common.request import Request
from emergence.common.response import Response
from emergence.core.event import Event, EventType
from emergence.core.process_definition import ProcessDefinition
from emergence.core.state import ProcessState
from emergence.executor.executor import Executor
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.security.capabilities import (
    MESSAGE_SEND,
    STATE_READ,
    STATE_WRITE,
)
from emergence.security.errors import PermissionDeniedError
from emergence.security.gated_state_store import GatedStateStore
from emergence.security.security_manager import SecurityManager


class TestSecurityManager:
    def test_require_raises_when_capability_missing(self):
        capabilities = create_kernel_context().capabilities
        security = SecurityManager(capabilities)

        with pytest.raises(PermissionDeniedError) as exc_info:
            security.require("pid-1", STATE_WRITE)

        assert exc_info.value.pid == "pid-1"
        assert exc_info.value.capability == STATE_WRITE

    def test_require_passes_when_capability_granted(self):
        ctx = create_kernel_context()
        ctx.capabilities.grant("pid-1", STATE_WRITE)

        ctx.security.require("pid-1", STATE_WRITE)


class TestGatedStateStore:
    def test_read_without_capability_raises(self):
        from emergence.events.event_bus import EventBus
        from emergence.kernel.state_store import StateStore

        event_bus = EventBus()
        ctx = create_kernel_context()
        store = StateStore(event_bus)
        gated = GatedStateStore(store, ctx.security, "no-read")

        with pytest.raises(PermissionDeniedError):
            gated.get("key")

    def test_write_without_capability_raises(self):
        from emergence.events.event_bus import EventBus
        from emergence.kernel.state_store import StateStore

        event_bus = EventBus()
        ctx = create_kernel_context()
        store = StateStore(event_bus)
        gated = GatedStateStore(store, ctx.security, "no-write")

        ctx.capabilities.grant("no-write", STATE_READ)

        with pytest.raises(PermissionDeniedError):
            gated.set("key", "value")

    def test_read_write_with_capabilities(self):
        from emergence.events.event_bus import EventBus
        from emergence.kernel.state_store import StateStore

        event_bus = EventBus()
        ctx = create_kernel_context()
        store = StateStore(event_bus)
        pid = "reader-writer"
        gated = GatedStateStore(store, ctx.security, pid)

        ctx.capabilities.grant(pid, STATE_READ)
        ctx.capabilities.grant(pid, STATE_WRITE)

        gated.set("answer", 42)
        assert gated.get("answer") == 42


class TestKernelPermissionEnforcement:
    def test_process_without_state_write_cannot_mutate(self):
        ctx = create_kernel_context()
        executor = Executor()

        class WriteAttemptRunner:
            def run(self, context):
                context.state.set("forbidden", True)

        definition = ProcessDefinition(
            name="restricted",
            implementation="restricted",
            version="1.0.0",
            required_permissions=frozenset(),
        )

        executor.register_runner("restricted", WriteAttemptRunner())
        ctx.registry.register(definition)

        kernel = Kernel(
            ctx=ctx,
            executor=executor,
            lifecycle=LifecycleManager(),
        )

        process = kernel.spawn(definition)
        pid = str(process.process_id)

        ctx.capabilities.revoke(pid, STATE_WRITE)

        kernel.run_next()

        assert process.state == ProcessState.FAILED
        assert "state.write" in process.failure_reason
        assert ctx.state.exists("forbidden") is False


class TestMessageRoundTrip:
    def test_send_emits_message_received_event(self):
        ctx = create_kernel_context()
        events: list = []

        ctx.event_bus.subscribe(
            EventType.MESSAGE_RECEIVED,
            lambda e: events.append(e),
        )

        ctx.mailboxes.create("sender")
        ctx.mailboxes.create("receiver")
        ctx.capabilities.grant("sender", MESSAGE_SEND)

        from emergence.security.gated_mailbox_manager import (
            GatedMailboxManager,
        )

        gated = GatedMailboxManager(
            ctx.mailboxes,
            ctx.security,
            "sender",
        )

        request = Request(
            sender_pid="sender",
            recipient_pid="receiver",
            action="research",
            payload={"query": "quantum computing"},
        )

        gated.send(request)

        assert len(events) == 1
        assert events[0].recipient_pid == "receiver"
        assert events[0].message.action == "research"

        received = ctx.mailboxes.receive("receiver")
        assert received is not None
        assert received.action == "research"

    def test_request_response_correlation(self):
        ctx = create_kernel_context()

        correlation = "corr-123"
        request = Request(
            sender_pid="a",
            recipient_pid="b",
            action="compute",
            payload={"x": 1},
            correlation_id=correlation,
        )

        response = Response(
            sender_pid="b",
            recipient_pid="a",
            payload={"result": 2},
            correlation_id=correlation,
            result=2,
        )

        assert request.correlation_id == response.correlation_id
        assert isinstance(request, Message)
