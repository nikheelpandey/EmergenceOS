"""
Tests for emergence.kernel.lifecycle.LifecycleManager.
"""

from __future__ import annotations

import pytest

from emergence.core.process import Process
from emergence.core.process_definition import ProcessDefinition
from emergence.core.state import ProcessState
from emergence.kernel.lifecycle import LifecycleManager


@pytest.fixture
def lifecycle() -> LifecycleManager:
    return LifecycleManager()


@pytest.fixture
def process() -> Process:
    definition = ProcessDefinition(
        name="test",
        implementation="fake",
        version="1.0.0",
    )
    return Process(definition=definition)


class TestLifecycleManager:
    def test_ready_transitions_created_to_ready(
        self,
        lifecycle: LifecycleManager,
        process: Process,
    ):
        lifecycle.ready(process)

        assert process.state == ProcessState.READY

    def test_start_transitions_ready_to_running(
        self,
        lifecycle: LifecycleManager,
        process: Process,
    ):
        lifecycle.ready(process)

        lifecycle.start(process)

        assert process.state == ProcessState.RUNNING

    def test_complete_transitions_running_to_completed(
        self,
        lifecycle: LifecycleManager,
        process: Process,
    ):
        lifecycle.ready(process)
        lifecycle.start(process)

        lifecycle.complete(process)

        assert process.state == ProcessState.COMPLETED

    def test_fail_transitions_running_to_failed(
        self,
        lifecycle: LifecycleManager,
        process: Process,
    ):
        lifecycle.ready(process)
        lifecycle.start(process)

        lifecycle.fail(process, "boom")

        assert process.state == ProcessState.FAILED
        assert process.failure_reason == "boom"

    def test_invalid_transition_raises_value_error(
        self,
        lifecycle: LifecycleManager,
        process: Process,
    ):
        with pytest.raises(
            ValueError,
            match="Invalid transition created -> completed",
        ):
            lifecycle.complete(process)
