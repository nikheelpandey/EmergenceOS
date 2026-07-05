"""Tests for emergence.core goal/plan/task models — M12."""

from __future__ import annotations

import pytest

from emergence.core.goal import Goal
from emergence.core.plan import Plan
from emergence.core.task import Task
from emergence.core.ids import GoalID, PlanID
from emergence.core.state import GoalState, PlanState, TaskState


class TestGoal:
    def test_transition_to_planning(self):
        goal = Goal(description="test")
        goal.transition_to(GoalState.PLANNING)
        assert goal.state == GoalState.PLANNING

    def test_invalid_transition_raises(self):
        goal = Goal(description="test")
        with pytest.raises(ValueError):
            goal.transition_to(GoalState.COMPLETED)


class TestPlan:
    def test_transition_to_active(self):
        plan = Plan(goal_id=GoalID.new())
        plan.transition_to(PlanState.ACTIVE)
        assert plan.state == PlanState.ACTIVE


class TestTask:
    def test_transition_to_ready(self):
        task = Task(
            plan_id=PlanID.new(),
            name="t1",
            process_definition_name="worker",
        )
        task.transition_to(TaskState.READY)
        assert task.state == TaskState.READY
