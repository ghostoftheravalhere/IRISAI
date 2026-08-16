"""Phase 7A Critical End-to-End Correctness Tests.

Verifies canonical action mapping accuracy and semantic action result validation.
"""

from __future__ import annotations

from backend.agent.agent_core import AgentCore
from backend.agent.planner import Planner


def test_canonical_action_right_click():
    planner = Planner()
    plan = planner.create_plan("Right click.", [])
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "desktop_tool"
    assert plan.steps[0].params["action"] == "right_click"


def test_canonical_action_double_click():
    planner = Planner()
    plan = planner.create_plan("Double click.", [])
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "desktop_tool"
    assert plan.steps[0].params["action"] == "double_click"


def test_canonical_action_copy_variants():
    planner = Planner()
    for prompt in ["Copy.", "Copy it", "Copy this"]:
        plan = planner.create_plan(prompt, [])
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "desktop_tool"
        assert plan.steps[0].params["action"] == "copy"


def test_canonical_action_paste_variants():
    planner = Planner()
    for prompt in ["Paste.", "Paste it", "Paste this"]:
        plan = planner.create_plan(prompt, [])
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "desktop_tool"
        assert plan.steps[0].params["action"] == "paste"


def test_canonical_action_scroll_variants():
    planner = Planner()
    plan_down = planner.create_plan("Scroll down.", [])
    assert plan_down.steps[0].params["action"] == "scroll_down"

    plan_up = planner.create_plan("Scroll up.", [])
    assert plan_up.steps[0].params["action"] == "scroll_up"


def test_canonical_action_type_text():
    planner = Planner()
    plan = planner.create_plan("Type hello.", [])
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "desktop_tool"
    assert plan.steps[0].params["action"] == "type_text"
    assert plan.steps[0].params["text"] == "hello."


def test_application_target_extraction():
    planner = Planner()
    cases = [
        ("Open Chrome.", "chrome"),
        ("Open Notepad.", "notepad"),
        ("Launch Google Chrome", "chrome"),
        ("Start Chrome", "chrome"),
    ]
    for prompt, expected_target in cases:
        plan = planner.create_plan(prompt, [])
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "desktop_tool"
        assert plan.steps[0].params["action"] == "open_application"
        assert plan.steps[0].params["target"] == expected_target


def test_agent_core_executes_exact_canonical_actions():
    agent = AgentCore()

    # 1. Right click
    res = agent.process_goal("Right click.")
    assert res.success is True
    step, tool_res = res.task_state.history[0]
    assert step.params["action"] == "right_click"
    assert tool_res.data.get("canonical_action") == "RIGHT_CLICK"

    # 2. Double click
    res = agent.process_goal("Double click.")
    assert res.success is True
    step, tool_res = res.task_state.history[0]
    assert step.params["action"] == "double_click"
    assert tool_res.data.get("canonical_action") == "DOUBLE_CLICK"

    # 3. Copy
    res = agent.process_goal("Copy it")
    assert res.success is True
    step, tool_res = res.task_state.history[0]
    assert step.params["action"] == "copy"
    assert tool_res.data.get("canonical_action") == "COPY"

    # 4. Paste
    res = agent.process_goal("Paste it")
    assert res.success is True
    step, tool_res = res.task_state.history[0]
    assert step.params["action"] == "paste"
    assert tool_res.data.get("canonical_action") == "PASTE"

    # 5. Open Chrome
    res = agent.process_goal("Launch Google Chrome")
    assert res.success is True
    step, tool_res = res.task_state.history[0]
    assert step.params["action"] == "open_application"
    assert step.params["target"] == "chrome"
    assert tool_res.data.get("canonical_action") == "OPEN_APPLICATION"
