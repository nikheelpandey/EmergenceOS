"""
Tests for emergence.executor.python_runner.

This suite validates dynamic Python execution via importlib.

Key invariants:

- Correct module and function are resolved.
- Function is invoked with ProcessContext argument.
- Return value is passed through unchanged.
- Invalid module/function raises expected errors.
- Implementation string must follow "module:function" format.
"""

from __future__ import annotations

import pytest

from emergence.executor.python_runner import PythonRunner
from emergence.core.process_context import ProcessContext
from emergence.core.process_definition import ProcessDefinition
from tests.helpers import build_test_process_context


# ============================================================
# Fake module setup
# ============================================================

import types
import sys


def create_fake_module():
    module = types.ModuleType("fake_module")

    def handler(context):
        return f"handled:{context.process_id}"

    module.handler = handler

    sys.modules["fake_module"] = module


create_fake_module()


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def runner():
    return PythonRunner()


def make_context(implementation: str) -> ProcessContext:
    definition = ProcessDefinition(
        name="Test",
        implementation=implementation,
        version="1.0.0",
    )
    return build_test_process_context(definition)


# ============================================================
# Execution
# ============================================================

class TestPythonRunnerExecution:
    """
    Validates correct dynamic import and function execution.
    """

    def test_runs_function_and_returns_value(self, runner):
        context = make_context("fake_module:handler")

        result = runner.run(context)

        assert result.startswith("handled:")
        assert str(context.process_id) in result

    def test_passes_context_to_function(self, runner):
        captured = {}

        def handler(context):
            captured["context"] = context
            return "ok"

        module = types.ModuleType("temp_module")
        module.handler = handler
        sys.modules["temp_module"] = module

        context = make_context("temp_module:handler")

        runner.run(context)

        assert captured["context"] is context


# ============================================================
# Error handling
# ============================================================

class TestPythonRunnerErrors:
    """
    Ensures predictable failure modes.
    """

    def test_missing_module_raises_import_error(self, runner):
        context = make_context("non_existent_module:handler")

        with pytest.raises(ModuleNotFoundError):
            runner.run(context)

    def test_missing_function_raises_attribute_error(self, runner):
        module = types.ModuleType("bad_module")
        sys.modules["bad_module"] = module

        context = make_context("bad_module:no_such_function")

        with pytest.raises(AttributeError):
            runner.run(context)

    def test_invalid_implementation_format_raises(self, runner):
        context = make_context("invalid_format")

        with pytest.raises(ValueError):
            runner.run(context)


# ============================================================
# Edge cases
# ============================================================

class TestPythonRunnerEdgeCases:
    """
    Boundary behavior of dynamic execution.
    """

    def test_extra_colons_are_handled(self, runner):
        module = types.ModuleType("multi_module")

        def handler(context):
            return "ok"

        module.handler = handler
        sys.modules["multi_module"] = module

        context = make_context("multi_module:handler:extra")

        with pytest.raises(ValueError):
            runner.run(context)
