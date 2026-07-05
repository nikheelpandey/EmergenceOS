"""
Tests for emergence.executor.executor.

This suite validates the Executor as a deterministic
runner registry and delegation system.

Key invariants:

- Runners are registered uniquely per implementation.
- Duplicate registration is rejected.
- Execution delegates correctly to the proper runner.
- Missing runner raises a deterministic error.
- Registry state is isolated and resettable.
"""

from __future__ import annotations

import pytest

from emergence.executor.executor import (
    Executor,
    RunnerAlreadyRegisteredError,
    RunnerNotFoundError,
)
from emergence.core.process_definition import ProcessDefinition
from tests.helpers import build_test_process_context


# ============================================================
# Fake Runner
# ============================================================

class FakeRunner:
    """
    Deterministic test runner.

    Records whether it was called and with which context.
    """

    def __init__(self):
        self.calls = []

    def run(self, context: ProcessContext):
        self.calls.append(context)
        return f"ran:{context.process_id}"


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def executor():
    return Executor()


@pytest.fixture
def context():
    definition = ProcessDefinition(
        name="Test",
        implementation="fake",
        version="1.0.0",
    )
    return build_test_process_context(definition)


@pytest.fixture
def runner():
    return FakeRunner()


# ============================================================
# Runner Registry
# ============================================================

class TestRunnerRegistry:
    """
    Tests registration and lookup behavior.
    """

    def test_register_runner(self, executor, runner):
        executor.register_runner("fake", runner)

        assert executor.has_runner("fake") is True
        assert len(executor) == 1

    def test_duplicate_registration_raises(self, executor, runner):
        executor.register_runner("fake", runner)

        with pytest.raises(RunnerAlreadyRegisteredError):
            executor.register_runner("fake", runner)

    def test_unregister_runner(self, executor, runner):
        executor.register_runner("fake", runner)

        executor.unregister_runner("fake")

        assert executor.has_runner("fake") is False
        assert len(executor) == 0

    def test_unregister_nonexistent_is_noop(self, executor):
        executor.unregister_runner("missing")  # should not crash

        assert len(executor) == 0

    def test_registered_implementations(self, executor, runner):
        executor.register_runner("fake", runner)
        executor.register_runner("fake2", runner)

        assert set(executor.registered_implementations()) == {
            "fake",
            "fake2",
        }


# ============================================================
# Execution
# ============================================================

class TestExecution:
    """
    Ensures correct delegation to runners.
    """

    def test_execute_calls_runner(self, executor, runner, context):
        executor.register_runner("fake", runner)

        result = executor.execute(context)

        assert runner.calls == [context]
        assert result == f"ran:{context.process_id}"

    def test_execute_missing_runner_raises(self, executor, context):
        with pytest.raises(RunnerNotFoundError):
            executor.execute(context)


# ============================================================
# Isolation and reset
# ============================================================

class TestIsolation:
    """
    Ensures executor state does not leak across tests.
    """

    def test_clear_removes_all_runners(self, executor, runner):
        executor.register_runner("fake", runner)
        executor.register_runner("fake2", runner)

        executor.clear()

        assert len(executor) == 0
        assert executor.registered_implementations() == ()
