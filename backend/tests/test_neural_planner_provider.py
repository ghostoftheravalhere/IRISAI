"""Comprehensive Unit Tests for Neural Planner Provider Abstraction, Validation, Timeout, and Fallback."""

from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.agent.agent_core import AgentCore
from backend.agent.benchmark import BenchmarkTask, PlannerBenchmark
from backend.agent.planner import PlanValidationError, PlanValidator, Planner
from backend.agent.policy_engine import PolicyEngine
from backend.agent.tool_registry import ToolDescriptor, ToolRegistry
from backend.agent.tools.desktop_tool import DesktopTool
from backend.agent.tools.filesystem_tool import FilesystemTool
from backend.agent.tools.git_tool import GitTool
from backend.automation.action_engine import ActionEngine
from backend.automation.controller import DesktopController
from backend.brain.reasoning.provider import LocalNeuralPlannerProvider, MockPlannerProvider, OllamaPlannerProvider, PlannerProvider


@pytest.fixture
def available_tools() -> list[ToolDescriptor]:
    controller = DesktopController()
    action_engine = ActionEngine(desktop_controller=controller)
    dt = DesktopTool(action_engine=action_engine)
    ft = FilesystemTool()
    gt = GitTool()
    return [dt.descriptor, ft.descriptor, gt.descriptor]


def test_deterministic_planner_works(available_tools):
    """1. Deterministic planner decomposes goals using heuristic rules."""
    planner = Planner(provider=None)
    plan = planner.create_plan("Open Notepad and type hello", available_tools)
    assert len(plan.steps) == 2
    assert plan.steps[0].tool_name == "desktop_tool"
    assert plan.steps[0].params["target"] == "notepad"
    assert plan.steps[1].params["text"] == "hello"


def test_provider_selection_works(available_tools):
    """2. Planner correctly selects between provider and deterministic mode."""
    provider = LocalNeuralPlannerProvider(model_name="qwen2.5-1.5b")
    planner = Planner(provider=provider)
    assert planner.provider is provider
    assert planner.provider.name == "local_neural:qwen2.5-1.5b"

    plan = planner.create_plan("Open Chrome", available_tools)
    assert plan is not None
    assert len(plan.steps) >= 1


def test_structured_model_output_validation(available_tools):
    """3. Valid structured JSON plan string is correctly parsed into Plan and PlanSteps."""
    valid_json = json.dumps({
        "goal": "Custom Neural Request",
        "steps": [
            {
                "step_id": 1,
                "tool_name": "desktop_tool",
                "description": "Open VS Code application",
                "params": {"action": "open_application", "target": "vscode"}
            },
            {
                "step_id": 2,
                "tool_name": "git_tool",
                "description": "Check repository status",
                "params": {"action": "get_status"}
            }
        ]
    })

    plan = PlanValidator.validate(valid_json, "Custom Neural Request", available_tools)
    assert plan.goal == "Custom Neural Request"
    assert len(plan.steps) == 2
    assert plan.steps[0].tool_name == "desktop_tool"
    assert plan.steps[1].tool_name == "git_tool"


def test_malformed_json_rejection_and_fallback(available_tools):
    """4. Malformed JSON output is rejected and triggers fallback to deterministic planner."""
    malformed_provider = LocalNeuralPlannerProvider(
        inference_fn=lambda prompt, ctx: "{ invalid json structure"
    )
    planner = Planner(provider=malformed_provider, enable_fallback=True)

    plan = planner.create_plan("Open Notepad and type test", available_tools)
    assert len(plan.steps) == 2  # Fallback deterministic plan executed
    assert plan.steps[0].tool_name == "desktop_tool"

    # Verify error raised when fallback disabled
    strict_planner = Planner(provider=malformed_provider, enable_fallback=False)
    with pytest.raises(PlanValidationError):
        strict_planner.create_plan("Open Notepad and type test", available_tools)


def test_timeout_fallback(available_tools):
    """5. Slow provider execution exceeding timeout_seconds triggers fallback to deterministic planner."""
    def slow_inference(prompt, ctx):
        time.sleep(0.5)
        return json.dumps({"steps": [{"tool_name": "desktop_tool", "params": {"target": "slow"}}]})

    slow_provider = LocalNeuralPlannerProvider(inference_fn=slow_inference)
    planner = Planner(provider=slow_provider, timeout_seconds=0.1, enable_fallback=True)

    start = time.perf_counter()
    plan = planner.create_plan("Search web for Python release", available_tools)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.4  # Timed out quickly
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "web_search_tool"  # Fallback plan used


def test_unavailable_provider_fallback(available_tools):
    """6. Unavailable or failing provider triggers automatic fallback."""
    unavailable_provider = LocalNeuralPlannerProvider(is_available=False)
    planner = Planner(provider=unavailable_provider, enable_fallback=True)

    plan = planner.create_plan("Open project and continue", available_tools)
    assert len(plan.steps) == 2
    assert plan.steps[0].tool_name == "desktop_tool"
    assert plan.steps[1].tool_name == "filesystem_tool"


def test_tool_action_schema_validation(available_tools):
    """7. Provider referencing an unregistered tool causes validation error & fallback."""
    unregistered_tool_json = json.dumps({
        "steps": [
            {
                "tool_name": "non_existent_unregistered_tool",
                "description": "Execute magic operation",
                "params": {"magic": True}
            }
        ]
    })
    bad_tool_provider = LocalNeuralPlannerProvider(inference_fn=lambda p, c: unregistered_tool_json)
    planner = Planner(provider=bad_tool_provider, enable_fallback=True)

    plan = planner.create_plan("Check git status", available_tools)
    assert plan.steps[0].tool_name == "git_tool"  # Fallback to valid deterministic plan


def test_agent_core_receives_valid_neural_plan():
    """8. AgentCore works seamlessly with Planner configured with a neural provider."""
    mock_controller = MagicMock(spec=DesktopController)
    mock_controller.open_application.return_value = MagicMock(success=True, message="App launched")
    action_engine = ActionEngine(desktop_controller=mock_controller)

    valid_neural_json = json.dumps({
        "steps": [
            {
                "step_id": 1,
                "tool_name": "desktop_tool",
                "description": "Open Notepad",
                "params": {"action": "open_application", "target": "notepad"}
            }
        ]
    })
    neural_provider = LocalNeuralPlannerProvider(inference_fn=lambda p, c: valid_neural_json)
    neural_planner = Planner(provider=neural_provider)

    core = AgentCore(planner=neural_planner, action_engine=action_engine)
    res = core.process_goal("IRIS, open Notepad")

    assert res.success is True
    assert res.task_state.status.value == "COMPLETED"
    assert len(res.task_state.history) == 1


def test_existing_simple_commands_unchanged():
    """9. Simple commands remain completely unaffected by neural provider addition."""
    planner = Planner(provider=LocalNeuralPlannerProvider())
    plan = planner.create_plan("Open Chrome", [])
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "desktop_tool"


def test_planner_benchmark_eval(available_tools):
    """10. PlannerBenchmark evaluates valid JSON, tool selection, latency, and fallback rates."""
    planner = Planner(provider=None)
    benchmark = PlannerBenchmark()
    res = benchmark.run_eval(planner, available_tools)

    assert res.total_tasks >= 5
    assert res.valid_json_rate == 100.0
    assert res.fallback_rate == 0.0
    assert res.average_latency_ms >= 0.0
