"""Integration test: plugin discovery and execution — M11."""

from __future__ import annotations

import pytest

from emergence.core.event import EventType
from emergence.core.state import ProcessState
from emergence.kernel.boot_context import build_kernel


@pytest.mark.integration
class TestPluginIntegration:
    def test_drop_in_plugin_discovered_and_spawned(self):
        kernel = build_kernel(spawn="hello_world", load_plugins=True)
        definition = kernel.context.registry.get("hello_world")

        assert definition.metadata.get("plugin") is True
        assert kernel.process_count() == 1

    def test_plugin_execution_completes(self, capsys):
        kernel = build_kernel(spawn="hello_world", load_plugins=True)
        kernel.run()

        output = capsys.readouterr().out
        assert "Hello from plugin: hello_world" in output
        assert kernel.context.registry.exists("worker")

    def test_plugin_load_emits_event(self):
        kernel = build_kernel(spawn=None, load_plugins=True)
        events = kernel.context.event_store.query(
            event_type=EventType.PLUGIN_LOADED,
        )
        names = {e.payload["plugin"] for e in events}
        assert "hello_world" in names

    def test_plugin_without_capability_fails(self):
        kernel = build_kernel(
            spawn="hello_world",
            load_plugins=True,
            enable_supervisor=False,
        )

        process = kernel.context.process_table.all()[0]
        pid = str(process.process_id)
        kernel.context.capabilities.clear(pid)

        kernel.run_next()
        assert process.state == ProcessState.FAILED
