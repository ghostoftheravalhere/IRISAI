"""Unit tests for Adaptive Recovery Engine & Self-Healing Workflows Subsystem."""

from __future__ import annotations

from backend.agent.adaptive_recovery import AdaptiveRecoveryEngine, get_recovery_metrics
from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.workflow import TaskPlan, WorkflowEngine, WorkflowStep
from backend.perception.ui_automation_models import AccessibilityElement
from backend.perception.ui_change_detector import UIChangeDetector


class _FakeDesktopController:
    def open_chrome(self) -> bool:
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


def test_ui_change_detector_deltas():
    detector = UIChangeDetector()
    prev = [AccessibilityElement(name="Save", role="Button", bounding_rectangle=(10, 10, 50, 20))]
    curr = [
        AccessibilityElement(name="Save", role="Button", bounding_rectangle=(100, 100, 50, 20)),
        AccessibilityElement(name="Settings Dialog", role="Window", bounding_rectangle=(0, 0, 400, 300)),
    ]

    report = detector.detect_changes(prev, curr)
    assert len(report.new_windows) >= 1
    assert "Save" in report.moved_controls


def test_workflow_engine_partial_replanning_primitives():
    dispatcher = AutomationDispatcher(_FakeDesktopController())
    workflow = WorkflowEngine(automation_dispatcher=dispatcher, enabled=True)

    plan = TaskPlan(
        name="Replanning Plan",
        steps=[
            WorkflowStep(intent="OPEN_APPLICATION", target="chrome"),
            WorkflowStep(intent="CLICK_VISUAL_TEXT", target="Settings"),
        ],
    )

    new_step = WorkflowStep(intent="CLICK_VISUAL_TEXT", target="Preferences")
    assert workflow.replace_step(plan, 1, new_step) is True
    assert plan.steps[1].target == "Preferences"

    ins_step = WorkflowStep(intent="PRESS_KEY", params={"key": "esc"})
    assert workflow.insert_step(plan, 1, ins_step) is True
    assert len(plan.steps) == 3

    assert workflow.skip_step(plan, 1) is True
    assert len(plan.steps) == 2

    merge_repl = [WorkflowStep(intent="OPEN_APPLICATION", target="chrome")]
    assert workflow.merge_steps(plan, 0, 2, merge_repl) is True
    assert len(plan.steps) == 1


def test_adaptive_recovery_engine_self_healing():
    engine = AdaptiveRecoveryEngine()
    dispatcher = AutomationDispatcher(_FakeDesktopController())
    workflow = WorkflowEngine(automation_dispatcher=dispatcher, enabled=True)

    failed_step = WorkflowStep(intent="CLICK_VISUAL_TEXT", target="Settings")
    plan = TaskPlan(name="Recovery Plan", steps=[failed_step])

    res = engine.attempt_recovery(failed_step, 0, plan, workflow)
    assert res.success is True
    assert "recovered" in res.reason.lower()

    metrics = get_recovery_metrics()
    assert metrics["total_recoveries"] >= 1
    assert metrics["recovery_success_percent"] == 100.0
