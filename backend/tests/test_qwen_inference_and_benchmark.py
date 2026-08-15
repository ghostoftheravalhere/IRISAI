"""Phase 2 Unit Tests and Benchmark Evaluation for Qwen2.5-1.5B Local Model Integration."""

from __future__ import annotations

import json
import pathlib
import pytest

from backend.agent.benchmark import BenchmarkTask, PlannerBenchmark
from backend.agent.planner import PlanValidationError, PlanValidator, Planner
from backend.agent.tool_registry import ToolDescriptor
from backend.brain.reasoning.provider import LocalNeuralPlannerProvider


@pytest.fixture
def available_tools() -> list[ToolDescriptor]:
    return [
        ToolDescriptor(tool_id="desktop_tool", name="desktop_tool", description="Executes UI automation, mouse clicks, and keyboard actions"),
        ToolDescriptor(tool_id="filesystem_tool", name="filesystem_tool", description="Reads, searches, and inspects local files"),
        ToolDescriptor(tool_id="git_tool", name="git_tool", description="Inspects Git repository history and commits"),
        ToolDescriptor(tool_id="web_search_tool", name="web_search_tool", description="Performs web searches"),
        ToolDescriptor(tool_id="browser_tool", name="browser_tool", description="Controls web browser tabs and navigation"),
    ]


def test_qwen_gguf_model_file_exists():
    """1. Verify Qwen2.5-1.5B-Instruct-Q4_K_M GGUF model file is downloaded and present on disk."""
    model_path = pathlib.Path("backend/models/qwen2.5-1.5b-instruct-q4_k_m.gguf")
    assert model_path.exists(), f"Model file missing at '{model_path.absolute()}'"
    file_size_mb = model_path.stat().st_size / (1024 * 1024)
    assert 900 <= file_size_mb <= 1100, f"Expected ~940MB GGUF file, got {file_size_mb:.2f}MB"


def test_qwen_local_inference_prompts(available_tools):
    """2. Test isolated inference across all 6 required user prompts producing valid structured plans."""
    provider = LocalNeuralPlannerProvider(
        model_name="Qwen2.5-1.5B-Instruct-Q4_K_M",
        model_path="backend/models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
    )
    planner = Planner(provider=provider)

    test_prompts = [
        ("Open Chrome.", ["desktop_tool", "browser_tool"]),
        ("Open Notepad and type hello.", ["desktop_tool"]),
        ("Find my project report.", ["filesystem_tool"]),
        ("Check the repository and summarize recent work.", ["git_tool", "filesystem_tool"]),
        ("Search the web for Python 3.14 and summarize it.", ["web_search_tool", "browser_tool"]),
        ("Copy this and paste it there.", ["desktop_tool"]),
    ]

    for prompt, expected_tools in test_prompts:
        plan = planner.create_plan(prompt, available_tools)
        assert plan.goal == prompt
        assert len(plan.steps) >= 1
        used_tools = {step.tool_name for step in plan.steps}
        assert any(t in used_tools for t in expected_tools), f"Prompt '{prompt}' selected {used_tools}, expected {expected_tools}"


def test_json_strict_enforcement_and_rejection(available_tools):
    """3. Verify PlanValidator strictly rejects invalid JSON, prose, unknown tools, and missing steps."""
    # Invalid JSON syntax
    with pytest.raises(PlanValidationError):
        PlanValidator.validate("Here is the plan for opening Notepad: {steps: []}", "Open Notepad", available_tools)

    # Missing steps list
    with pytest.raises(PlanValidationError):
        PlanValidator.validate(json.dumps({"goal": "test"}), "test", available_tools)

    # Unregistered tool reference
    with pytest.raises(PlanValidationError):
        PlanValidator.validate(
            json.dumps({"goal": "test", "steps": [{"tool_name": "unknown_cyber_tool", "params": {}}]}),
            "test",
            available_tools,
        )


def test_planner_benchmark_evaluation(available_tools):
    """4. Run PlannerBenchmark comparing Deterministic Planner vs Qwen2.5-1.5B Local Planner."""
    benchmark = PlannerBenchmark()

    # Evaluates Deterministic Planner
    det_planner = Planner(provider=None)
    det_res = benchmark.run_eval(det_planner, available_tools)
    assert det_res.valid_json_rate == 100.0
    assert det_res.valid_schema_rate == 100.0

    # Evaluates Qwen Neural Planner
    qwen_provider = LocalNeuralPlannerProvider(
        model_name="Qwen2.5-1.5B-Instruct-Q4_K_M",
        model_path="backend/models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
    )
    qwen_planner = Planner(provider=qwen_provider)
    qwen_res = benchmark.run_eval(qwen_planner, available_tools)
    assert qwen_res.valid_json_rate == 100.0
    assert qwen_res.valid_schema_rate == 100.0
    assert qwen_res.tool_accuracy_rate >= 80.0
    assert qwen_res.fallback_rate == 0.0


def test_qwen_unavailable_fallback(available_tools):
    """5. Verify offline/unavailable Qwen provider falls back gracefully to deterministic planner."""
    offline_provider = LocalNeuralPlannerProvider(
        model_name="Qwen2.5-1.5B-Instruct-Q4_K_M",
        is_available=False,
    )
    planner = Planner(provider=offline_provider, enable_fallback=True)
    plan = planner.create_plan("Open Notepad and type hello.", available_tools)
    assert plan is not None
    assert len(plan.steps) >= 1
