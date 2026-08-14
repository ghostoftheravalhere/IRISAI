"""Unit tests for Agentic Task Execution & Goal Manager Subsystem."""

from __future__ import annotations

from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.workflow import WorkflowEngine
from backend.core.events.bus import EventBus
from backend.goals.goal_events import GoalCreatedEvent
from backend.goals.goal_manager import GoalManager
from backend.goals.goal_models import Goal, GoalStatus
from backend.goals.goal_planner import GoalPlanner
from backend.goals.goal_state_machine import GoalStateMachine


class _FakeDesktopController:
    def open_chrome(self) -> bool:
        return True

    def open_settings(self) -> bool:
        return True

    def open_application(self, name: str) -> bool:
        return True

    def wait_for_window(self, name: str, timeout_sec: float = 3.0) -> bool:
        return True

    def wait_for_window_active(self, name: str, timeout_sec: float = 3.0) -> bool:
        return True

    def wait_for_condition(self, condition_func, timeout_sec: float = 5.0, poll_interval_sec: float = 0.05, description: str = "condition") -> bool:
        return True

    def activate_window(self, name: str) -> bool:
        return True

    def is_window_active(self, name: str) -> bool:
        return True

    def hotkey(self, *keys: str) -> bool:
        return True

    def type_text(self, text: str) -> bool:
        return True

    def press(self, key: str) -> bool:
        return True


def test_goal_state_machine_transitions():
    goal = Goal(name="Test Goal")
    assert goal.status == GoalStatus.CREATED

    # Valid transitions
    assert GoalStateMachine.transition(goal, GoalStatus.PLANNING) is True
    assert GoalStateMachine.transition(goal, GoalStatus.EXECUTING) is True
    assert GoalStateMachine.transition(goal, GoalStatus.COMPLETED) is True

    # Illegal transition from COMPLETED
    assert GoalStateMachine.transition(goal, GoalStatus.EXECUTING) is False


def test_goal_planner_decomposition():
    planner = GoalPlanner()
    goal = Goal(name="Prepare my study environment")

    plans = planner.plan_goal(goal)
    assert len(plans) == 2
    assert "Search Engine" in plans[0].name


def test_goal_manager_end_to_end_execution():
    fake_desktop = _FakeDesktopController()
    dispatcher = AutomationDispatcher(fake_desktop)
    workflow_engine = WorkflowEngine(automation_dispatcher=dispatcher, enabled=True)
    event_bus = EventBus()

    events_received = []

    def _on_event(e):
        events_received.append(e)

    event_bus.subscribe(GoalCreatedEvent, _on_event)

    manager = GoalManager(workflow_engine=workflow_engine, event_bus=event_bus)
    goal = manager.create_goal("Prepare my study environment")

    assert goal.status == GoalStatus.CREATED
    assert len(events_received) == 1

    success = manager.plan_and_execute(goal.goal_id)
    assert success is True
    assert goal.status == GoalStatus.COMPLETED
    assert goal.completed_at is not None
