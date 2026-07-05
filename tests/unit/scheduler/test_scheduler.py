"""
Tests for emergence.scheduler.Scheduler — M4 scheduling.
"""

from __future__ import annotations

import pytest

from emergence.core.ids import ProcessID
from emergence.core.wait_condition import WaitCondition
from emergence.events.event_bus import EventBus
from emergence.scheduler.scheduler import Scheduler, SchedulerEmptyError


class AlwaysSatisfied(WaitCondition):
    def is_satisfied(self) -> bool:
        return True


class NeverSatisfied(WaitCondition):
    def is_satisfied(self) -> bool:
        return False


@pytest.fixture
def scheduler() -> Scheduler:
    return Scheduler(EventBus())


class TestPriorityQueue:
    def test_higher_priority_runs_first(self, scheduler: Scheduler):
        low = ProcessID.new()
        high = ProcessID.new()

        scheduler.enqueue(low, priority=1)
        scheduler.enqueue(high, priority=10)

        assert scheduler.dequeue() == high
        assert scheduler.dequeue() == low

    def test_fifo_within_same_priority(self, scheduler: Scheduler):
        first = ProcessID.new()
        second = ProcessID.new()

        scheduler.enqueue(first, priority=5)
        scheduler.enqueue(second, priority=5)

        assert scheduler.dequeue() == first
        assert scheduler.dequeue() == second


class TestWaiting:
    def test_waiting_process_not_in_queue(self, scheduler: Scheduler):
        pid = ProcessID.new()
        scheduler.enqueue(pid)
        scheduler.mark_waiting(pid, NeverSatisfied())

        assert scheduler.is_empty() is True
        assert scheduler.is_waiting(pid) is True

    def test_satisfied_condition_wakes_process(self, scheduler: Scheduler):
        pid = ProcessID.new()
        woken: list[ProcessID] = []

        scheduler._on_wake = woken.append  # noqa: SLF001
        scheduler.enqueue(pid)
        scheduler.mark_waiting(pid, AlwaysSatisfied())

        woken_ids = scheduler.evaluate_waiting()

        assert pid in woken_ids
        assert scheduler.is_waiting(pid) is False
        assert scheduler.contains(pid) is True


class TestDependencies:
    def test_process_not_enqueued_until_deps_complete(
        self,
        scheduler: Scheduler,
    ):
        dep = ProcessID.new()
        dependent = ProcessID.new()

        scheduler.enqueue(dependent, depends_on=(dep,))

        assert scheduler.is_empty() is True
        assert dependent in scheduler.pending_dependency_ids()

        released = scheduler.notify_completed(dep)

        assert dependent in released
        assert scheduler.contains(dependent) is True

    def test_multiple_dependencies(self, scheduler: Scheduler):
        dep_a = ProcessID.new()
        dep_b = ProcessID.new()
        dependent = ProcessID.new()

        scheduler.enqueue(dependent, depends_on=(dep_a, dep_b))
        scheduler.notify_completed(dep_a)

        assert scheduler.is_empty() is True

        scheduler.notify_completed(dep_b)

        assert scheduler.contains(dependent) is True


class TestDequeue:
    def test_dequeue_empty_raises(self, scheduler: Scheduler):
        with pytest.raises(SchedulerEmptyError):
            scheduler.dequeue()
