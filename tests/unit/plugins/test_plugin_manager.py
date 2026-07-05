"""Tests for emergence.plugins — M11."""

from __future__ import annotations

from pathlib import Path

import pytest

from emergence.core.event import EventType
from emergence.events.event_bus import EventBus
from emergence.executor.executor import Executor
from emergence.kernel.registry import ProcessRegistry
from emergence.plugins.loader import load_manifest, parse_simple_yaml
from emergence.plugins.manager import (
    PluginAlreadyLoadedError,
    PluginManager,
    PluginNotFoundError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLUGINS_ROOT = PROJECT_ROOT / "plugins"


@pytest.fixture
def plugin_manager() -> PluginManager:
    return PluginManager(
        registry=ProcessRegistry(),
        executor=Executor(),
        event_bus=EventBus(),
        plugins_root=PLUGINS_ROOT,
    )


class TestPluginLoader:
    def test_parse_simple_yaml(self):
        text = """
name: test
version: 1.0.0
required_capabilities:
  - tool.python
  - state.read
"""
        data = parse_simple_yaml(text)
        assert data["name"] == "test"
        assert data["required_capabilities"] == [
            "tool.python",
            "state.read",
        ]

    def test_load_hello_world_manifest(self):
        manifest = load_manifest(
            PLUGINS_ROOT / "hello_world" / "plugin.yaml"
        )
        assert manifest.name == "hello_world"
        assert "tool.python" in manifest.required_capabilities


class TestPluginManager:
    def test_discover_finds_plugins(self, plugin_manager: PluginManager):
        manifests = plugin_manager.discover()
        names = {m.name for m in manifests}
        assert "hello_world" in names
        assert "worker" in names

    def test_load_registers_definition(self, plugin_manager: PluginManager):
        events = []
        plugin_manager.event_bus.subscribe(
            EventType.PLUGIN_LOADED,
            lambda e: events.append(e),
        )

        definition = plugin_manager.load(
            PLUGINS_ROOT / "hello_world"
        )

        assert definition.name == "hello_world"
        assert plugin_manager.registry.exists("hello_world")
        assert len(events) == 1

    def test_load_all(self, plugin_manager: PluginManager):
        definitions = plugin_manager.load_all()
        assert len(definitions) >= 3

    def test_unload(self, plugin_manager: PluginManager):
        plugin_manager.load(PLUGINS_ROOT / "hello_world")
        plugin_manager.unload("hello_world")

        with pytest.raises(PluginNotFoundError):
            plugin_manager.get("hello_world")

    def test_duplicate_load_raises(self, plugin_manager: PluginManager):
        plugin_manager.load(PLUGINS_ROOT / "hello_world")
        with pytest.raises(PluginAlreadyLoadedError):
            plugin_manager.load(PLUGINS_ROOT / "hello_world")
