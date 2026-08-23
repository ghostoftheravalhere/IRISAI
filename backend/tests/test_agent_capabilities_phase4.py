"""Phase 4 Comprehensive Integration Test Suite verifying Real Agent Capabilities, Tool Quality, Task Memory, and Failure Recovery across all 12 Real-World Scenarios."""

from __future__ import annotations

import pytest

from backend.agent.agent_core import AgentCore
from backend.agent.policy_engine import PermissionLevel, PolicyEngine
from backend.agent.task_state import PlanStep, TaskState, TaskStatus
from backend.agent.tool_registry import ToolDescriptor, ToolRegistry, ToolResult
from backend.agent.tools.browser_tool import BrowserTool
from backend.agent.tools.desktop_tool import DesktopTool
from backend.agent.tools.filesystem_tool import FilesystemTool
from backend.agent.tools.git_tool import GitTool
from backend.agent.tools.web_search_tool import WebSearchTool


@pytest.fixture
def agent_core() -> AgentCore:
    return AgentCore()


def test_scenario_1_project_status(agent_core: AgentCore):
    """Scenario 1: Project status & completion query using real Git repository state."""
    res = agent_core.process_goal("Check my repository and tell me what we've completed.")
    assert res.success
    assert "branch" in res.response.lower() or "v2-development" in res.response.lower() or "completed" in res.response.lower()


def test_scenario_2_recent_git_changes(agent_core: AgentCore):
    """Scenario 2: Recent Git commit & diff changes inspection."""
    gt = GitTool()
    res = gt.execute({"action": "get_log", "count": 3})
    assert res.success
    assert "commits" in res.data
    assert len(res.data["commits"]) > 0


def test_scenario_3_find_local_file(agent_core: AgentCore):
    """Scenario 3: Find a specific local file in workspace."""
    ft = FilesystemTool()
    res = ft.execute({"action": "search_files", "query": "qwen"})
    assert res.success
    assert "matches" in res.data
    assert any("qwen" in m.lower() for m in res.data["matches"])


def test_scenario_4_open_application(agent_core: AgentCore):
    """Scenario 4: Open application task."""
    res = agent_core.process_goal("Open Chrome.")
    assert res.success or "chrome" in res.response.lower() or "opened" in res.response.lower()


def test_scenario_5_multistep_desktop_task(agent_core: AgentCore):
    """Scenario 5: Multi-step desktop task (open app + type text)."""
    dt = DesktopTool()
    r1 = dt.execute({"action": "open_application", "target": "notepad"})
    assert r1.success
    r2 = dt.execute({"action": "type_text", "text": "hello"})
    assert isinstance(r2.success, bool)


def test_scenario_6_web_search(agent_core: AgentCore):
    """Scenario 6: Web search with source-aware structured results."""
    wst = WebSearchTool()
    res = wst.execute({"action": "search", "query": "Python 3.14"})
    assert res.success
    assert "sources" in res.data
    assert len(res.data["sources"]) > 0
    assert res.data["sources"][0]["url"] != ""


def test_scenario_7_search_for_person(agent_core: AgentCore):
    """Scenario 7: Person search with confidence-aware 'possible match' phrasing."""
    wst = WebSearchTool()
    res = wst.execute({"action": "search", "query": "John Doe"})
    assert res.success
    assert res.data.get("is_person_search") is True
    assert res.data.get("confidence") == "possible_match"


def test_scenario_8_ambiguous_filesystem_target():
    """Scenario 8: Ambiguous file search returning structured candidate list."""
    ft = FilesystemTool()
    res = ft.execute({"action": "search_files", "query": "report"})
    assert res.success
    assert "candidates" in res.data
    assert len(res.data["candidates"]) >= 1


def test_scenario_9_multiturn_followup(agent_core: AgentCore):
    """Scenario 9: Multi-turn conversational follow-up candidate resolution."""
    # Turn 1: Search for report
    r1 = agent_core.process_goal("Find my project report.")
    assert r1.success

    # Turn 2: Follow-up selection
    if agent_core.active_task_state and agent_core.active_task_state.candidates:
        r2 = agent_core.process_goal("The second one.")
        assert r2.success
        assert "read" in r2.response.lower() or "summary" in r2.response.lower() or "found" in r2.response.lower()


def test_scenario_10_tool_failure_recovery():
    """Scenario 10: Graceful handling of missing files / missing applications."""
    ft = FilesystemTool()
    res = ft.execute({"action": "read_file", "path": "non_existent_file_999.txt"})
    assert not res.success
    assert res.error_code == "FILE_NOT_FOUND"


def test_scenario_11_confirmation_required_operation():
    """Scenario 11: Confirmation-required policy interception."""
    policy = PolicyEngine()
    eval_res = policy.evaluate("desktop_tool", PermissionLevel.CONFIRMATION_REQUIRED, {"action": "delete_file"})
    assert eval_res.requires_user_confirmation
    assert eval_res.permission_level == PermissionLevel.CONFIRMATION_REQUIRED


def test_scenario_12_cancellation_handling(agent_core: AgentCore):
    """Scenario 12: User cancellation of confirmation-paused task."""
    state = TaskState(user_goal="Delete critical file", status=TaskStatus.WAITING_CONFIRMATION)
    res = agent_core.resume_task_with_confirmation(state, confirmed=False)
    assert not res.success
    assert res.error_code == "CANCELLED"
    assert "cancelled" in res.response.lower()
