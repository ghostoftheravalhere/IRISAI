"""Comprehensive Unit & Integration Test Suite for Agent Core and Tool-Using Architecture."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
import pytest

from backend.agent.agent_core import AgentCore, AgentResult
from backend.agent.planner import Plan, Planner, PlanStep
from backend.agent.policy_engine import PermissionLevel, PolicyEngine
from backend.agent.task_state import TaskState, TaskStatus
from backend.agent.tool_executor import ToolExecutor
from backend.agent.tool_registry import Tool, ToolDescriptor, ToolRegistry, ToolResult
from backend.agent.tools.desktop_tool import DesktopTool
from backend.agent.tools.filesystem_tool import FilesystemTool
from backend.agent.tools.git_tool import GitTool
from backend.agent.tools.web_search_tool import WebSearchTool
from backend.automation.action_engine import ActionEngine, ActionResult, CanonicalAction
from backend.automation.controller import DesktopController
from backend.core.di.container import build_container
from backend.config.settings import Settings


# --- Mock Custom Tool for Testing Protocol ---
class MockCustomTool:
    """Test custom tool implementation."""

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id="mock_custom_tool",
            name="mock_custom_tool",
            description="Mock tool for agent testing",
            permission_level=PermissionLevel.CONFIRMATION_REQUIRED,
            input_schema={"action": "test"},
        )

    def execute(self, params: dict[str, Any], task_state: TaskState | None = None) -> ToolResult:
        return ToolResult(True, "Mock custom tool executed successfully", data={"param": params.get("action")})


@pytest.fixture
def agent_container():
    """Build fresh AppContainer with mocked DesktopController side-effects."""
    settings = Settings(APP_ENV="testing")
    container = build_container(settings)

    mock_open_app = MagicMock(return_value=True)
    mock_click = MagicMock(return_value=True)
    mock_hotkey = MagicMock(return_value=True)

    container.desktop_controller.open_application = mock_open_app
    container.desktop_controller.click = mock_click
    container.desktop_controller.hotkey = mock_hotkey
    container.canonical_action_engine._desktop_controller.open_application = mock_open_app
    container.canonical_action_engine._desktop_controller.click = mock_click
    container.canonical_action_engine._desktop_controller.hotkey = mock_hotkey

    return container


# =========================================================================
# 1. TOOL REGISTRY & EXECUTOR TESTS
# =========================================================================

def test_tool_registry_registration():
    """Verify tool registration and descriptor listing."""
    reg = ToolRegistry()
    tool = MockCustomTool()
    assert reg.register_tool(tool) is True
    assert reg.has_tool("mock_custom_tool") is True
    assert reg.get_tool("mock_custom_tool") is not None
    descriptors = reg.list_descriptors()
    assert len(descriptors) == 1
    assert descriptors[0].name == "mock_custom_tool"


def test_tool_executor_safe_execution():
    """Verify safe tool execution passes policy engine."""
    reg = ToolRegistry()
    tool = FilesystemTool()
    reg.register_tool(tool)
    executor = ToolExecutor(reg)

    res, policy = executor.execute_tool("filesystem_tool", {"action": "exists", "path": "."})
    assert policy.allowed is True
    assert policy.permission_level == PermissionLevel.SAFE
    assert res.success is True
    assert "Path exists" in res.message


def test_tool_executor_policy_confirmation():
    """Verify tool with CONFIRMATION_REQUIRED stops for confirmation."""
    reg = ToolRegistry()
    tool = MockCustomTool()
    reg.register_tool(tool)
    executor = ToolExecutor(reg)

    res, policy = executor.execute_tool("mock_custom_tool", {"action": "test"})
    assert policy.requires_user_confirmation is True
    assert res.error_code == "CONFIRMATION_REQUIRED"
    assert res.success is False


def test_policy_engine_blocked_command():
    """Verify policy engine blocks destructive commands."""
    engine = PolicyEngine()
    eval_res = engine.evaluate("shell_tool", PermissionLevel.SAFE, {"cmd": "rm -rf /"})
    assert eval_res.allowed is False
    assert eval_res.permission_level == PermissionLevel.BLOCKED


# =========================================================================
# 2. FILESYSTEM & GIT TOOL BOUNDARY TESTS
# =========================================================================

def test_filesystem_tool_workspace_boundary():
    """Verify FilesystemTool rejects paths outside workspace boundary."""
    fs = FilesystemTool(workspace_root=os.getcwd())
    res = fs.execute({"action": "read_file", "path": "../../Windows/System32/drivers/etc/hosts"})
    assert res.success is False
    assert "Access denied" in res.message
    assert res.error_code == "SECURITY_VIOLATION"


def test_git_tool_read_only_status():
    """Verify GitTool status execution."""
    git_tool = GitTool()
    res = git_tool.execute({"action": "get_status"})
    assert res.success is True
    assert "Branch" in res.message


# =========================================================================
# 3. PLANNER & FEEDBACK REASONING TESTS
# =========================================================================

def test_planner_github_goal_plan():
    """Verify Planner creates multi-step plan for repository query."""
    planner = Planner()
    plan = planner.create_plan("Open my GitHub repository and tell me what we've completed", [])
    assert len(plan.steps) == 3
    assert plan.steps[0].tool_name == "git_tool"
    assert plan.steps[1].tool_name == "git_tool"
    assert plan.steps[2].tool_name == "filesystem_tool"


def test_planner_replan_on_file_not_found():
    """Verify dynamic replan reasoning on FILE_NOT_FOUND error."""
    planner = Planner()
    step = PlanStep(1, "filesystem_tool", "Read missing file", {"action": "read_file", "path": "nonexistent.txt"})
    result = ToolResult(False, "File not found", error_code="FILE_NOT_FOUND")
    state = TaskState(user_goal="Find report")
    state.current_plan = Plan(goal="Find report", steps=[step])

    decision = planner.evaluate_step_result(step, result, state)
    assert decision == "REPLAN"
    assert len(state.current_plan.steps) == 2
    assert state.current_plan.steps[1].params["action"] == "search_files"


# =========================================================================
# 4. AGENT CORE END-TO-END ORCHESTRATION TESTS
# =========================================================================

def test_agent_core_single_step_task(agent_container):
    """Test single-step goal execution through AgentCore."""
    core = agent_container.agent_core
    res = core.process_goal("Search online for Python 3.12 release notes")
    assert res.success is True
    assert "searched online" in res.response.lower() or "completed" in res.response.lower()
    assert res.task_state.status == TaskStatus.COMPLETED


def test_agent_core_multi_step_github_task(agent_container):
    """Test multi-step GitHub repository status goal execution."""
    core = agent_container.agent_core
    res = core.process_goal("Open my GitHub repository and tell me what we've completed")
    assert res.success is True
    assert res.task_state.status == TaskStatus.COMPLETED
    assert len(res.task_state.history) == 3


def test_agent_core_confirmation_flow(agent_container):
    """Test security confirmation prompt and user resume flow."""
    core = agent_container.agent_core
    core.register_custom_tool(MockCustomTool())

    # Step 1: Execute goal with confirmation-required tool
    with patch.object(core._planner, "create_plan") as mock_plan:
        step = PlanStep(1, "mock_custom_tool", "Execute custom action", {"action": "test"})
        mock_plan.return_value = Plan(goal="Run custom action", steps=[step])

        res1 = core.process_goal("Run custom action")
        assert res1.success is False
        assert res1.error_code == "CONFIRMATION_REQUIRED"
        assert "Do you want me to proceed?" in res1.response
        assert res1.task_state.status == TaskStatus.WAITING_CONFIRMATION

        # Step 2: Resume with rejection (user says No)
        res_cancel = core.resume_task_with_confirmation(res1.task_state, confirmed=False)
        assert res_cancel.success is False
        assert res_cancel.error_code == "CANCELLED"

        # Step 3: Resume with confirmation (user says Yes)
        res_confirm = core.resume_task_with_confirmation(res1.task_state, confirmed=True)
        assert res_confirm.success is True
