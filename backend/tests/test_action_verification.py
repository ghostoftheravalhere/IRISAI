"""Unit tests for Self-Verifying Automation & Action Verification Subsystem."""

from __future__ import annotations

from backend.agent.agent_models import AgentObservation
from backend.agent.verification_engine import VerificationEngine, get_verification_metrics
from backend.automation.dispatcher import AutomationDispatcher
from backend.automation.verification_models import ActionVerificationPolicy
from backend.brain.workflow import TaskPlan, WorkflowEngine, WorkflowStep


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

    def browser_search(self, application: str, query: str) -> bool:
        return True


def test_open_application_verification_strategy():
    verifier = VerificationEngine()
    obs = AgentObservation(active_app="Chrome", visible_text="Google Search", dialogue_state="IDLE", memory_summary="", workspace_name="")

    policy = ActionVerificationPolicy(verification_type="OPEN_APPLICATION")
    res = verifier.verify_action("OPEN_APPLICATION", "chrome", policy=policy, obs_after=obs)

    assert res.success is True
    assert res.confidence >= 0.90


def test_click_visual_text_verification_strategy():
    verifier = VerificationEngine()
    obs_before = AgentObservation(active_app="System", visible_text="Click Submit", dialogue_state="IDLE", memory_summary="", workspace_name="")
    obs_after = AgentObservation(active_app="System", visible_text="Form Saved Successfully", dialogue_state="IDLE", memory_summary="", workspace_name="")

    policy = ActionVerificationPolicy(verification_type="CLICK_VISUAL_TEXT")
    res = verifier.verify_action("CLICK_VISUAL_TEXT", "Submit", policy=policy, obs_before=obs_before, obs_after=obs_after)

    assert res.success is True
    assert "Visual delta" in res.reason


def test_search_browser_and_run_tests_verification_strategies():
    verifier = VerificationEngine()

    res_search = verifier.verify_action("SEARCH_BROWSER", "ChatGPT")
    assert res_search.success is True

    res_tests = verifier.verify_action("RUN_TESTS", "pytest")
    assert res_tests.success is True


def test_workflow_engine_verification_integration():
    dispatcher = AutomationDispatcher(_FakeDesktopController())
    verifier = VerificationEngine()
    workflow = WorkflowEngine(automation_dispatcher=dispatcher, enabled=True, verification_engine=verifier)

    plan = TaskPlan(
        name="Self-Verifying Plan",
        steps=[
            WorkflowStep(intent="OPEN_APPLICATION", target="chrome"),
            WorkflowStep(intent="SEARCH_BROWSER", target="chrome", params={"query": "ChatGPT"}),
        ],
    )

    success = workflow.execute_plan(plan)
    assert success is True

    metrics = get_verification_metrics()
    assert metrics["total_verifications"] >= 2
    assert metrics["success_rate_percent"] == 100.0
