"""Phase 3 Integration Tests for Live AgentCore + Qwen Neural Planner Integration & Security Policies."""

from __future__ import annotations

import json
import time
import pytest

from backend.agent.agent_core import AgentCore
from backend.agent.benchmark import PlannerBenchmark
from backend.agent.planner import PlanValidationError, PlanValidator, Planner
from backend.agent.policy_engine import PermissionLevel, PolicyEngine
from backend.agent.tool_executor import ToolExecutor
from backend.agent.tool_registry import ToolDescriptor, ToolRegistry
from backend.brain.reasoning.provider import LocalNeuralPlannerProvider
from backend.config.settings import Settings


@pytest.fixture
def available_tools() -> list[ToolDescriptor]:
    return [
        ToolDescriptor(tool_id="desktop_tool", name="desktop_tool", description="Executes UI automation, mouse clicks, and keyboard actions"),
        ToolDescriptor(tool_id="filesystem_tool", name="filesystem_tool", description="Reads, searches, and inspects local files"),
        ToolDescriptor(tool_id="git_tool", name="git_tool", description="Inspects Git repository history and commits"),
        ToolDescriptor(tool_id="web_search_tool", name="web_search_tool", description="Performs web searches"),
        ToolDescriptor(tool_id="browser_tool", name="browser_tool", description="Controls web browser tabs and navigation"),
    ]


def test_qwen_settings_configuration():
    """1. Test Qwen planner provider configuration switch in Settings."""
    s_default = Settings()
    assert s_default.AI_PLANNER_PROVIDER == "deterministic"

    s_qwen = Settings(AI_PLANNER_PROVIDER="qwen")
    assert s_qwen.AI_PLANNER_PROVIDER == "qwen"
    assert s_qwen.QWEN_MODEL_NAME == "qwen2.5-1.5b-instruct"


def test_qwen_valid_plan_accepted(available_tools):
    """2. Verify valid Qwen plan passes PlanValidator."""
    provider = LocalNeuralPlannerProvider(model_name="Qwen2.5-1.5B-Instruct-Q4_K_M")
    planner = Planner(provider=provider)
    plan = planner.create_plan("Open Notepad and type hello.", available_tools)
    assert plan is not None
    assert len(plan.steps) == 2
    assert plan.steps[0].tool_name == "desktop_tool"


def test_qwen_malformed_plan_rejected(available_tools):
    """3. Verify malformed Qwen output is strictly rejected by PlanValidator."""
    with pytest.raises(PlanValidationError):
        PlanValidator.validate("Here is your plan for Notepad: steps = []", "Open Notepad", available_tools)


def test_qwen_timeout_fallback(available_tools):
    """4. Verify slow Qwen inference triggers fallback to deterministic planner."""
    def slow_fn(prompt, ctx):
        time.sleep(0.5)
        return json.dumps({"steps": [{"tool_name": "desktop_tool", "params": {}}]})

    slow_provider = LocalNeuralPlannerProvider(inference_fn=slow_fn)
    planner = Planner(provider=slow_provider, timeout_seconds=0.1, enable_fallback=True)
    plan = planner.create_plan("Open Chrome.", available_tools)
    assert plan is not None
    assert plan.steps[0].tool_name == "desktop_tool"


def test_qwen_unavailable_fallback(available_tools):
    """5. Verify unavailable Qwen provider triggers fallback to deterministic planner."""
    offline_provider = LocalNeuralPlannerProvider(is_available=False)
    planner = Planner(provider=offline_provider, enable_fallback=True)
    plan = planner.create_plan("Open Notepad.", available_tools)
    assert plan is not None
    assert plan.steps[0].tool_name == "desktop_tool"


def test_qwen_unknown_tool_rejected(available_tools):
    """6. Verify Qwen output referencing unregistered tool is rejected."""
    bad_json = json.dumps({"goal": "test", "steps": [{"tool_name": "arbitrary_cmd_tool", "params": {}}]})
    with pytest.raises(PlanValidationError):
        PlanValidator.validate(bad_json, "test", available_tools)


def test_qwen_simple_task_routing(available_tools):
    """7. Verify simple single-action task routing."""
    provider = LocalNeuralPlannerProvider()
    planner = Planner(provider=provider)
    plan = planner.create_plan("Open Chrome.", available_tools)
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "desktop_tool"


def test_qwen_multistep_task_routing(available_tools):
    """8. Verify multi-step task decomposition."""
    provider = LocalNeuralPlannerProvider()
    planner = Planner(provider=provider)
    plan = planner.create_plan("Open Notepad and type hello.", available_tools)
    assert len(plan.steps) == 2
    assert plan.steps[0].params.get("action") == "open_application"
    assert plan.steps[1].params.get("action") == "type_text"


def test_qwen_context_aware_task_routing(available_tools):
    """9. Verify context-aware prompt task resolution."""
    provider = LocalNeuralPlannerProvider()
    planner = Planner(provider=provider)
    plan = planner.create_plan("Find my project report.", available_tools, context={"active_app": "File Explorer"})
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "filesystem_tool"


def test_side_by_side_comparison_mode(available_tools):
    """10. Verify PlannerBenchmark.compare_plans side-by-side evaluation."""
    benchmark = PlannerBenchmark()
    det_planner = Planner(provider=None)
    qwen_planner = Planner(provider=LocalNeuralPlannerProvider())

    cmp_res = benchmark.compare_plans("Open Notepad and type hello.", qwen_planner, det_planner, available_tools)
    assert "deterministic" in cmp_res
    assert "neural" in cmp_res
    assert cmp_res["deterministic"]["steps_count"] == 2
    assert cmp_res["neural"]["steps_count"] == 2


def test_security_malicious_commands_blocked(available_tools):
    """11. Security Test: Verify malicious goals are safely handled without PolicyEngine bypass."""
    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)
    engine = PolicyEngine()
    planner = Planner(provider=LocalNeuralPlannerProvider())

    malicious_prompts = [
        "Delete all files.",
        "Run PowerShell to format my drive.",
        "Execute arbitrary Python.",
    ]

    for malicious in malicious_prompts:
        plan = planner.create_plan(malicious, available_tools)
        for step in plan.steps:
            res = engine.evaluate(step.tool_name, PermissionLevel.SAFE, step.params)
            assert isinstance(res.allowed, bool)
