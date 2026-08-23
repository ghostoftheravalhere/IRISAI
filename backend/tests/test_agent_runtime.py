"""Unit tests for Autonomous Agent Runtime Subsystem."""

from __future__ import annotations

from backend.agent.observation_engine import ObservationEngine
from backend.agent.recovery_policy import RecoveryPolicy
from backend.agent.reflection_engine import ReflectionEngine
from backend.agent.verification_engine import VerificationEngine


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


def test_observation_and_verification_engines():
    obs_engine = ObservationEngine()
    obs = obs_engine.capture_observation(active_app="Chrome", visible_text="Google Search")

    assert obs.active_app == "Chrome"
    assert "Google" in obs.visible_text

    verifier = VerificationEngine()
    assert verifier.verify_step("Chrome", obs) is True


def test_reflection_and_recovery_policies():
    reflector = ReflectionEngine()
    obs1 = ObservationEngine().capture_observation("System")
    obs2 = ObservationEngine().capture_observation("Chrome")

    report = reflector.reflect("Open Chrome", True, obs1, obs2)
    assert report.success is True
    assert report.continue_plan is True

    recovery = RecoveryPolicy(max_retries=3)
    assert recovery.handle_failure(0) == "RETRY"
    assert recovery.handle_failure(3) == "REPLAN"
    assert recovery.handle_failure(4) == "AWAITING_HUMAN_APPROVAL"


from backend.agent.agent_core import AgentCore
from backend.automation.action_engine import ActionEngine
from backend.automation.controller import DesktopController

def test_agent_core_runtime():
    action_engine = ActionEngine(desktop_controller=DesktopController())
    core = AgentCore(action_engine=action_engine)
    res = core.process_goal("IRIS, open Notepad")
    assert res.success is True
