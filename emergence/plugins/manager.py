from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

from emergence.core.event import Event, EventType
from emergence.core.budget import ResourceBudget
from emergence.core.execution_spec import ExecutionSpec
from emergence.core.process_definition import ProcessDefinition
from emergence.events.event_bus import EventBus
from emergence.executor.executor import Executor
from emergence.executor.python_runner import PythonRunner
from emergence.kernel.registry import ProcessRegistry
from emergence.plugins.loader import discover_plugin_dirs, load_manifest
from emergence.plugins.manifest import PluginManifest


class PluginNotFoundError(Exception):
    """Raised when a requested plugin is not loaded."""


class PluginAlreadyLoadedError(Exception):
    """Raised when attempting to load a duplicate plugin."""


@dataclass
class LoadedPlugin:
    manifest: PluginManifest
    definition: ProcessDefinition
    module_name: str


@dataclass
class PluginManager:
    """
    Discovers, loads, and unloads process plugins.

    Each plugin directory contains a plugin.yaml manifest and
    an entrypoint module. Loaded plugins are registered as
    ProcessDefinitions with declared capabilities.
    """

    registry: ProcessRegistry
    executor: Executor
    event_bus: EventBus
    plugins_root: Path = field(
        default_factory=lambda: Path("plugins")
    )
    _loaded: dict[str, LoadedPlugin] = field(default_factory=dict)

    def discover(self) -> list[PluginManifest]:
        """Find all plugin manifests without loading them."""
        return [
            load_manifest(plugin_dir / "plugin.yaml")
            for plugin_dir in discover_plugin_dirs(self.plugins_root)
        ]

    def load(self, plugin_dir: Path) -> ProcessDefinition:
        """Load a single plugin from its directory."""
        manifest = load_manifest(plugin_dir / "plugin.yaml")

        if manifest.name in self._loaded:
            raise PluginAlreadyLoadedError(
                f"Plugin '{manifest.name}' is already loaded."
            )

        module_name = self._import_entrypoint(manifest, plugin_dir)
        target = f"{module_name}:{manifest.entrypoint.split(':')[-1]}"

        spec = ExecutionSpec(
            runner=manifest.runner,
            target=target,
            config=dict(manifest.config),
        )

        definition = ProcessDefinition(
            name=manifest.name,
            description=manifest.description,
            version=manifest.version,
            execution_spec=spec,
            default_budget=ResourceBudget(
                max_execution_time_seconds=manifest.max_execution_time_seconds,
            ),
            required_permissions=manifest.required_capabilities,
            metadata={
                "plugin": True,
                "supported_events": sorted(manifest.supported_events),
            },
        )

        if manifest.runner == "python":
            self.executor.register_runner(target, PythonRunner())

        self.registry.register(definition)
        self._loaded[manifest.name] = LoadedPlugin(
            manifest=manifest,
            definition=definition,
            module_name=module_name,
        )

        self._publish(EventType.PLUGIN_LOADED, manifest.name, {
            "version": manifest.version,
            "entrypoint": manifest.entrypoint,
        })

        return definition

    def load_all(self) -> list[ProcessDefinition]:
        """Discover and load every plugin in plugins_root."""
        definitions: list[ProcessDefinition] = []
        for plugin_dir in discover_plugin_dirs(self.plugins_root):
            definitions.append(self.load(plugin_dir))
        return definitions

    def unload(self, name: str) -> None:
        """Unload a plugin and remove its ProcessDefinition."""
        loaded = self._loaded.pop(name, None)
        if loaded is None:
            raise PluginNotFoundError(f"Plugin '{name}' is not loaded.")

        self.registry.unregister(name)
        self.executor.unregister_runner(
            loaded.definition.runner_key
        )

        module_name = loaded.module_name
        sys.modules.pop(module_name, None)

        self._publish(EventType.PLUGIN_UNLOADED, name, {})

    def loaded_names(self) -> tuple[str, ...]:
        return tuple(self._loaded.keys())

    def get(self, name: str) -> ProcessDefinition:
        loaded = self._loaded.get(name)
        if loaded is None:
            raise PluginNotFoundError(f"Plugin '{name}' is not loaded.")
        return loaded.definition

    def _import_entrypoint(
        self,
        manifest: PluginManifest,
        plugin_dir: Path,
    ) -> str:
        module_file, _, func_name = manifest.entrypoint.partition(":")
        if not func_name:
            raise ValueError(
                f"Invalid entrypoint '{manifest.entrypoint}' "
                f"for plugin '{manifest.name}'."
            )

        module_path = plugin_dir / f"{module_file}.py"
        if not module_path.exists():
            raise FileNotFoundError(
                f"Plugin entrypoint not found: {module_path}"
            )

        module_name = f"emergence_plugin_{manifest.name}"
        spec = importlib.util.spec_from_file_location(
            module_name,
            module_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError(
                f"Cannot load plugin module from {module_path}"
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        if not hasattr(module, func_name):
            raise AttributeError(
                f"Plugin '{manifest.name}' entrypoint "
                f"'{func_name}' not found in {module_path}"
            )

        return module_name

    def _publish(
        self,
        event_type: EventType,
        plugin_name: str,
        payload: dict,
    ) -> None:
        self.event_bus.publish(
            Event(
                event_type=event_type,
                payload={"plugin": plugin_name, **payload},
            )
        )
