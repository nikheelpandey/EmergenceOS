"""
Tests for emergenceos.core.ids.

Architectural Contract
----------------------
Identifiers are immutable, strongly typed value objects that uniquely identify
kernel entities.

These tests protect the following invariants:

* Every generated ID is globally unique.
* IDs are immutable.
* IDs are hashable.
* IDs compare by value.
* Different ID types are never considered equal.
* IDs round-trip correctly through string serialization.
* String and repr representations remain stable.
"""

from uuid import UUID

import pytest

from emergence.core.ids import (
    BaseID,
    ProcessID,
    ProcessDefinitionID,
    GoalID,
    PlanID,
    TaskID,
    EventID,
    CheckpointID,
)


# ============================================================================
# BaseID
# ============================================================================


class TestBaseIDConstruction:
    """
    Verify construction and serialization behavior.

    These tests ensure IDs can be safely created and serialized across
    process boundaries.
    """

    def test_new_generates_uuid(self):
        identifier = BaseID.new()

        assert isinstance(identifier.value, UUID)

    def test_new_generates_unique_ids(self):
        id1 = BaseID.new()
        id2 = BaseID.new()

        assert id1 != id2

    def test_from_string_recreates_same_identifier(self):
        original = BaseID.new()

        recreated = BaseID.from_string(str(original))

        assert recreated == original
        assert recreated.value == original.value

    def test_from_string_invalid_uuid_raises(self):
        with pytest.raises(ValueError):
            BaseID.from_string("not-a-valid-uuid")


class TestEquality:
    """
    IDs are value objects.

    Equality is determined solely by the wrapped UUID and concrete type.
    """

    def test_same_uuid_same_type_are_equal(self):
        identifier = BaseID.new()

        recreated = BaseID.from_string(str(identifier))

        assert recreated == identifier

    def test_different_uuid_not_equal(self):
        assert BaseID.new() != BaseID.new()

    def test_different_types_with_same_uuid_are_not_equal(self):
        uuid = UUID("12345678-1234-5678-1234-567812345678")

        process = ProcessID(uuid)
        goal = GoalID(uuid)

        assert process != goal


class TestHashing:
    """
    IDs must be usable as dictionary keys and set members.
    """

    def test_ids_are_hashable(self):
        identifier = BaseID.new()

        mapping = {identifier: "kernel"}

        assert mapping[identifier] == "kernel"

    def test_equal_ids_have_same_hash(self):
        identifier = BaseID.new()
        recreated = BaseID.from_string(str(identifier))

        assert hash(identifier) == hash(recreated)


class TestImmutability:
    """
    IDs must never change after creation.

    Immutability is essential because IDs are frequently used as keys in
    dictionaries throughout the kernel.
    """

    def test_value_cannot_be_modified(self):
        identifier = BaseID.new()

        with pytest.raises(AttributeError):
            identifier.value = UUID("12345678-1234-5678-1234-567812345678")


class TestStringRepresentations:
    """
    Human-readable representations should remain stable.

    These are commonly used for logging and debugging.
    """

    def test_str_returns_uuid_string(self):
        identifier = BaseID.new()

        assert str(identifier) == str(identifier.value)

    def test_repr_contains_class_name(self):
        identifier = ProcessID.new()

        representation = repr(identifier)

        assert "ProcessID" in representation
        assert str(identifier.value) in representation


# ============================================================================
# Strongly Typed IDs
# ============================================================================


@pytest.mark.parametrize(
    "id_cls",
    [
        ProcessID,
        ProcessDefinitionID,
        GoalID,
        PlanID,
        TaskID,
        EventID,
        CheckpointID,
    ],
)
class TestTypedIdentifiers:
    """
    Every identifier subclass should inherit the complete behavior of BaseID.

    These tests ensure all typed IDs preserve the guarantees expected by the
    rest of the kernel.
    """

    def test_new_returns_correct_type(self, id_cls):
        identifier = id_cls.new()

        assert isinstance(identifier, id_cls)

    def test_round_trip_serialization(self, id_cls):
        original = id_cls.new()

        recreated = id_cls.from_string(str(original))

        assert recreated == original

    def test_instances_are_hashable(self, id_cls):
        identifier = id_cls.new()

        mapping = {identifier: "value"}

        assert mapping[identifier] == "value"

    def test_instances_are_unique(self, id_cls):
        id1 = id_cls.new()
        id2 = id_cls.new()

        assert id1 != id2