"""
Tests for emergence.core.process_definition.

Architectural Contract
----------------------
A ProcessDefinition is an immutable blueprint describing how a Process
should be created.

It contains no runtime state and is safe to share throughout the kernel.

These tests protect the following invariants:

* Process definitions are immutable.
* Required fields are validated.
* Default values remain stable.
* Qualified names are generated correctly.
* Permission lookups behave correctly.
* Value object semantics are preserved.
"""

from dataclasses import FrozenInstanceError

import pytest

from emergence.core.budget import ResourceBudget
from emergence.core.ids import ProcessDefinitionID
from emergence.core.process_definition import ProcessDefinition


# ============================================================================
# Construction
# ============================================================================


class TestConstruction:
    """
    Verify valid ProcessDefinition construction.

    These tests ensure process definitions correctly capture the static
    information required by the kernel to create runtime processes.
    """

    def test_minimal_process_definition(self):
        definition = ProcessDefinition(
            name="Planner",
            implementation="planner.process",
        )

        assert isinstance(
            definition.process_definition_id,
            ProcessDefinitionID,
        )
        assert definition.name == "Planner"
        assert definition.description == ""
        assert definition.version == "1.0.0"
        assert definition.implementation == "planner.process"
        assert isinstance(
            definition.default_budget,
            ResourceBudget,
        )
        assert definition.required_permissions == frozenset()
        assert definition.metadata == {}

    def test_custom_process_definition(self):
        budget = ResourceBudget(max_tokens=5000)

        permissions = frozenset(
            {
                "state.read",
                "state.write",
            }
        )

        metadata = {
            "category": "planning",
            "owner": "kernel",
        }

        definition = ProcessDefinition(
            name="Planner",
            description="Creates execution plans.",
            version="2.1.0",
            implementation="planner.process",
            default_budget=budget,
            required_permissions=permissions,
            metadata=metadata,
        )

        assert definition.description == "Creates execution plans."
        assert definition.version == "2.1.0"
        assert definition.default_budget == budget
        assert definition.required_permissions == permissions
        assert definition.metadata == metadata


# ============================================================================
# Validation
# ============================================================================


class TestValidation:
    """
    Process definitions must reject incomplete or invalid configurations.

    The kernel should never accept a definition that cannot be executed.
    """

    @pytest.mark.parametrize(
        "name",
        [
            "",
            "   ",
            "\t",
            "\n",
        ],
    )
    def test_empty_name_raises(self, name):
        with pytest.raises(
            ValueError,
            match="ProcessDefinition.name cannot be empty.",
        ):
            ProcessDefinition(
                name=name,
                implementation="planner.process",
            )

    @pytest.mark.parametrize(
        "implementation",
        [
            "",
            "   ",
            "\t",
            "\n",
        ],
    )
    def test_empty_implementation_raises(
        self,
        implementation,
    ):
        with pytest.raises(
            ValueError,
            match="ProcessDefinition requires implementation or execution_spec.",
        ):
            ProcessDefinition(
                name="Planner",
                implementation=implementation,
            )

    @pytest.mark.parametrize(
        "version",
        [
            "",
            "   ",
            "\t",
            "\n",
        ],
    )
    def test_empty_version_raises(self, version):
        with pytest.raises(
            ValueError,
            match="ProcessDefinition.version cannot be empty.",
        ):
            ProcessDefinition(
                name="Planner",
                implementation="planner.process",
                version=version,
            )


# ============================================================================
# Qualified Name
# ============================================================================


class TestQualifiedName:
    """
    The qualified name uniquely identifies a process definition version.
    """

    def test_qualified_name(self):
        definition = ProcessDefinition(
            name="Planner",
            version="3.0.1",
            implementation="planner.process",
        )

        assert definition.qualified_name == "Planner@3.0.1"


# ============================================================================
# Permission Handling
# ============================================================================


class TestPermissions:
    """
    ProcessDefinition exposes convenience methods for querying required
    permissions.
    """

    def test_has_permission_returns_true(self):
        definition = ProcessDefinition(
            name="Planner",
            implementation="planner.process",
            required_permissions=frozenset(
                {
                    "state.read",
                    "state.write",
                }
            ),
        )

        assert definition.has_permission("state.read")

    def test_has_permission_returns_false(self):
        definition = ProcessDefinition(
            name="Planner",
            implementation="planner.process",
            required_permissions=frozenset(
                {
                    "state.read",
                }
            ),
        )

        assert not definition.has_permission("tool.execute")


# ============================================================================
# Immutability
# ============================================================================


class TestImmutability:
    """
    ProcessDefinition is immutable once created.

    Runtime behavior should never modify the blueprint from which
    processes are instantiated.
    """

    def test_definition_is_immutable(self):
        definition = ProcessDefinition(
            name="Planner",
            implementation="planner.process",
        )

        with pytest.raises(FrozenInstanceError):
            definition.name = "Executor"


# ============================================================================
# Representation
# ============================================================================


class TestRepresentation:
    """
    repr(ProcessDefinition) should provide useful debugging information.
    """

    def test_repr_contains_key_fields(self):
        definition = ProcessDefinition(
            name="Planner",
            version="2.0.0",
            implementation="planner.process",
        )

        representation = repr(definition)

        assert "ProcessDefinition(" in representation
        assert "Planner" in representation
        assert "2.0.0" in representation
        assert "planner.process" in representation


# ============================================================================
# Value Object Behaviour
# ============================================================================


class TestValueObjectBehavior:
    """
    ProcessDefinition behaves as an immutable value object.
    """

    def test_equal_definitions_compare_equal(self):
        identifier = ProcessDefinitionID.new()

        budget = ResourceBudget()

        definition1 = ProcessDefinition(
            process_definition_id=identifier,
            name="Planner",
            implementation="planner.process",
            default_budget=budget,
        )

        definition2 = ProcessDefinition(
            process_definition_id=identifier,
            name="Planner",
            implementation="planner.process",
            default_budget=budget,
        )

        assert definition1 == definition2

    def test_process_definition_with_metadata_is_not_hashable(self):
        definition = ProcessDefinition(
            name="Planner",
            implementation="planner.process",
        )

        with pytest.raises(TypeError):
            {definition: "planner"}

    def test_different_definitions_are_not_equal(self):
        definition1 = ProcessDefinition(
            name="Planner",
            implementation="planner.process",
        )

        definition2 = ProcessDefinition(
            name="Executor",
            implementation="executor.process",
        )

        assert definition1 != definition2