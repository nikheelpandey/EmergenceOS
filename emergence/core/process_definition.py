"""
core/process_definition.py

Defines the immutable ProcessDefinition model.

A ProcessDefinition is a blueprint for creating Process instances.
It describes what a process is, but contains no runtime state.

The Kernel is responsible for resolving the implementation identifier
to an executable runtime component.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from emergence.core.budget import ResourceBudget
from emergence.core.ids import ProcessDefinitionID


@dataclass(frozen=True, slots=True)
class ProcessDefinition:
    """
    Immutable blueprint for creating Process instances.

    Attributes
    ----------
    process_definition_id:
        Unique identifier for this process definition.

    name:
        Human-readable name.

    description:
        Short description of the process.

    version:
        Semantic version of this definition.

    implementation:
        Identifier understood by the Kernel that resolves
        to the executable implementation.

    default_budget:
        Default resource limits assigned to newly created
        Process instances.

    required_permissions:
        Permissions required before this process may execute.

    metadata:
        Arbitrary application-specific metadata.
    """

    process_definition_id: ProcessDefinitionID = field(
        default_factory=ProcessDefinitionID.new
    )

    name: str = ""

    description: str = ""

    version: str = "1.0.0"

    implementation: str = ""

    default_budget: ResourceBudget = field(
        default_factory=ResourceBudget
    )

    required_permissions: frozenset[str] = field(
        default_factory=frozenset
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        """
        Validate the process definition.
        """

        if not self.name.strip():
            raise ValueError("ProcessDefinition.name cannot be empty.")

        if not self.implementation.strip():
            raise ValueError(
                "ProcessDefinition.implementation cannot be empty."
            )

        if not self.version.strip():
            raise ValueError(
                "ProcessDefinition.version cannot be empty."
            )

    @property
    def qualified_name(self) -> str:
        """
        Return the fully qualified name of this definition.

        Example:
            Planner@1.0.0
        """

        return f"{self.name}@{self.version}"

    def has_permission(self, permission: str) -> bool:
        """
        Return True if the process requires the given permission.
        """

        return permission in self.required_permissions

    def __repr__(self) -> str:
        return (
            f"ProcessDefinition("
            f"name='{self.name}', "
            f"version='{self.version}', "
            f"implementation='{self.implementation}')"
        )