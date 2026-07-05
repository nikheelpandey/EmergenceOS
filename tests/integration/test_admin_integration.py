"""
Integration tests for the live kernel admin control plane (M19).
"""

from __future__ import annotations

import os
import threading
import time

import pytest

from emergence.admin.client import AdminClient
from emergence.admin.runtime_lock import RuntimeLock
from emergence.admin.server import AdminServer
from emergence.cli.__main__ import main
from emergence.core.process_context import ProcessContext
from emergence.core.process_definition import ProcessDefinition
from emergence.core.state import ProcessState
from emergence.executor.executor import Executor
from emergence.kernel.boot_context import create_kernel_context
from emergence.kernel.kernel import Kernel
from emergence.kernel.lifecycle import LifecycleManager
from emergence.kernel.runtime import RuntimeService
from tests.helpers_admin import short_data_dir


class ApprovalRunner:
    def run(self, context: ProcessContext) -> str:
        if not context.state.get("approval:approve-me"):
            context.wait_for_approval(
                "approve-me",
                message="please approve",
            )
        return "approved"


def _start_admin_for_kernel(
    kernel: Kernel,
    monkeypatch,
) -> tuple[AdminServer, RuntimeLock]:
    data_dir = short_data_dir("integration")
    monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))
    lock = RuntimeLock.create()
    lock.acquire()
    admin = AdminServer(kernel)
    admin.start()
    lock.publish_manifest(host=admin.host, port=admin.port)
    return admin, lock


@pytest.mark.integration
class TestAdminIntegration:
    def test_runtime_service_exposes_admin_snapshot(self, monkeypatch):
        data_dir = short_data_dir("runtime1")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        service = RuntimeService.start()
        try:
            client = AdminClient.connect()
            snapshot = client.snapshot()

            assert snapshot["os_status"] == "running"
            names = {item["name"] for item in snapshot["processes"]}
            assert "heartbeat" in names
            assert "event_collector" in names
            assert "job_worker" in names
        finally:
            service.stop()

    def test_cli_ps_connects_to_live_runtime(self, monkeypatch, capsys):
        data_dir = short_data_dir("runtime2")
        monkeypatch.setenv("EMERGENCE_DATA_DIR", str(data_dir))

        service = RuntimeService.start()
        try:
            assert main(["ps"]) == 0
            output = capsys.readouterr().out
            assert "heartbeat" in output
        finally:
            service.stop()

    def test_cli_ps_without_runtime_shows_helpful_error(self, capsys):
        assert main(["ps"]) == 1
        err = capsys.readouterr().err
        assert "not running" in err.lower()

    def test_approve_unblocks_waiting_process(self, monkeypatch):
        ctx = create_kernel_context()
        executor = Executor()
        executor.register_runner("approval_runner", ApprovalRunner())
        definition = ProcessDefinition(
            name="approval_runner",
            implementation="approval_runner",
            version="1.0.0",
        )
        ctx.registry.register(definition)

        kernel = Kernel(
            ctx=ctx,
            executor=executor,
            lifecycle=LifecycleManager(),
        )

        admin, lock = _start_admin_for_kernel(kernel, monkeypatch)
        process = kernel.spawn(definition)

        runner = threading.Thread(target=kernel.run_forever, daemon=True)
        runner.start()

        try:
            deadline = time.time() + 3.0
            while time.time() < deadline:
                if process.state == ProcessState.WAITING:
                    break
                time.sleep(0.05)

            assert process.state == ProcessState.WAITING

            client = AdminClient.connect()
            snapshot = client.snapshot()
            pending = snapshot["pending_approvals"]
            assert any(item["request_id"] == "approve-me" for item in pending)

            client.approve("approve-me")

            deadline = time.time() + 3.0
            while time.time() < deadline:
                if process.state == ProcessState.COMPLETED:
                    break
                time.sleep(0.05)

            assert process.state == ProcessState.COMPLETED
        finally:
            kernel.shutdown()
            admin.stop()
            lock.release()

    def test_demo_mode_still_works_without_runtime(self, capsys):
        assert main(["ps", "--demo"]) == 0
        output = capsys.readouterr().out
        assert "EmergenceOS process monitor" in output
