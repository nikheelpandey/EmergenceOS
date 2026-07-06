"""
An ID should:
    Be globally unique.
    Be immutable.
    Be hashable (so it can be used as a dictionary key).
    Be type-safe (ProcessID should not be interchangeable with GoalID).
    Be serializable.
    Have a nice string representation.
    Hide the underlying UUID implementation.
    Be easy to generate.

"""


from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class BaseID:
    """
    Base class for all strongly typed identifiers.

    IDs are immutable value objects that wrap a UUID.
    Subclasses provide semantic meaning and improve type safety.
    """

    value: UUID = field(default_factory=uuid4)

    @classmethod
    def new(cls) -> "BaseID":
        """Create a new identifier."""
        return cls()

    @classmethod
    def from_string(cls, value: str) -> "BaseID":
        """Construct an ID from its string representation."""
        return cls(UUID(value))

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.value})"


# ---------------------------------------------------------------------
# Strongly typed identifiers
# ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProcessID(BaseID):
    """Unique identifier for a Process."""


@dataclass(frozen=True, slots=True)
class ProcessDefinitionID(BaseID):
    """Unique identifier for a ProcessDefinition."""


@dataclass(frozen=True, slots=True)
class GoalID(BaseID):
    """Unique identifier for a Goal."""


@dataclass(frozen=True, slots=True)
class PlanID(BaseID):
    """Unique identifier for a Plan."""


@dataclass(frozen=True, slots=True)
class TaskID(BaseID):
    """Unique identifier for a Task."""


@dataclass(frozen=True, slots=True)
class EventID(BaseID):
    """Unique identifier for an Event."""


@dataclass(frozen=True, slots=True)
class CheckpointID(BaseID):
    """Unique identifier for a Checkpoint."""


@dataclass(frozen=True, slots=True)
class ArtifactID(BaseID):
    """Unique identifier for a physical Artifact."""