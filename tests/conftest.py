"""
Shared pytest fixtures for EmergenceOS.

Every reusable object should be constructed here rather than duplicated
throughout the test suite.

Goals
-----
* Keep individual tests extremely small.
* Provide deterministic objects.
* Avoid unnecessary mocks.
* Encourage behavior-driven testing.
"""

from __future__ import annotations

import pytest

# These imports will be uncommented as each module is implemented.
#
# from emergenceos.events.event_bus import EventBus
# from emergenceos.kernel.kernel import Kernel
# from emergenceos.scheduler.scheduler import Scheduler
# from emergenceos.executor.executor import Executor
# from emergenceos.kernel.state_store import StateStore
#
# from tests.fakes.fake_clock import FakeClock
# from tests.fakes.fake_runner import FakeRunner


@pytest.fixture
def fake_clock():
    """
    Provides a deterministic clock.

    Architectural invariant
    -----------------------
    Tests must never depend on wall-clock time.

    Every timestamp observed by the kernel should originate from an
    injectable clock implementation.
    """
    # return FakeClock()
    raise NotImplementedError("FakeClock has not been implemented yet.")


@pytest.fixture
def fake_runner():
    """
    Provides a deterministic process runner.

    The fake runner records invocations and optionally returns a
    configurable result, allowing tests to verify executor behavior
    without executing arbitrary Python code.
    """
    # return FakeRunner()
    raise NotImplementedError("FakeRunner has not been implemented yet.")