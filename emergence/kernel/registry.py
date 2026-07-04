"""
kernel/registry.py

Registry of ProcessDefinitions.

The Registry owns immutable ProcessDefinitions and allows
the Kernel to look them up by name.
"""

from __future__ import annotations

from typing import Dict, Iterable

from emergence.core.process_definition import ProcessDefinition


class ProcessDefinitionAlreadyRegisteredError(Exception):
    """Raised when attempting to register a duplicate ProcessDefinition."""


class ProcessDefinitionNotFoundError(Exception):
    """Raised when a ProcessDefinition cannot be found."""


class ProcessRegistry:
    """
    Registry of all available ProcessDefinitions.
    """

    def __init__(self) -> None:
        self._definitions: Dict[str, ProcessDefinition] = {}

    def register(self, definition: ProcessDefinition) -> None:
        """
        Register a ProcessDefinition.
        """
        if definition.name in self._definitions:
            raise ProcessDefinitionAlreadyRegisteredError(
                f"'{definition.name}' is already registered."
            )

        self._definitions[definition.name] = definition

    def unregister(self, name: str) -> None:
        """
        Remove a ProcessDefinition.
        """
        self._definitions.pop(name, None)

    def get(self, name: str) -> ProcessDefinition:
        """
        Retrieve a ProcessDefinition by name.
        """
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise ProcessDefinitionNotFoundError(
                f"Unknown process '{name}'."
            ) from exc

    def exists(self, name: str) -> bool:
        return name in self._definitions

    def all(self) -> tuple[ProcessDefinition, ...]:
        return tuple(self._definitions.values())

    def clear(self) -> None:
        self._definitions.clear()

    def __len__(self) -> int:
        return len(self._definitions)