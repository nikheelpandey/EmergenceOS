"""
Unit tests for the admin server request dispatch.
"""

from __future__ import annotations

import json
import socket

import pytest

from emergence.admin.client import AdminClient
from emergence.admin.server import AdminServer
from emergence.core.process_definition import ProcessDefinition
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager


@pytest.mark.unit
class TestAdminServer:
    def test_snapshot_and_approve_over_tcp(self):
        ctx = create_kernel_context()
        kernel = Kernel(ctx=ctx, executor=ctx.executor, lifecycle=LifecycleManager())
        definition = ProcessDefinition(
            name="worker",
            implementation="worker",
            version="1.0.0",
        )
        ctx.registry.register(definition)
        kernel.spawn(definition)

        server = AdminServer(kernel)
        server.start()

        try:
            client = AdminClient.from_address(server.host, server.port)
            snapshot = client.snapshot()
            assert len(snapshot["processes"]) == 1

            ping = client.ping()
            assert ping["status"] == "ok"

            approved = client.approve("req-123")
            assert approved["granted"] is True
            assert ctx.state.get("approval:req-123") is True
        finally:
            server.stop()

    def test_unknown_method_returns_error(self):
        ctx = create_kernel_context()
        kernel = Kernel(ctx=ctx, executor=ctx.executor, lifecycle=LifecycleManager())
        server = AdminServer(kernel)
        server.start()

        try:
            with socket.create_connection((server.host, server.port)) as conn:
                payload = {
                    "id": "1",
                    "method": "nope",
                    "params": {},
                }
                conn.sendall((json.dumps(payload) + "\n").encode("utf-8"))
                raw = conn.recv(4096).decode("utf-8").strip()
                response = json.loads(raw)
                assert response["ok"] is False
                assert "unknown method" in response["error"]
        finally:
            server.stop()
