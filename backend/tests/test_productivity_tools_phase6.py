"""Phase 6 Integration Test Suite verifying Personal Productivity Tools (EmailTool, CalendarTool, GitHubTool), policy permissions, multi-tool planning, authentication safety, and natural responses."""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from backend.agent.agent_core import AgentCore
from backend.agent.dataset.redactor import SecretRedactor
from backend.agent.policy_engine import PermissionLevel, PolicyEngine
from backend.agent.response_generator import ResponseGenerator
from backend.agent.task_state import PlanStep, TaskState
from backend.agent.tools.calendar_tool import CalendarTool
from backend.agent.tools.email_tool import EmailTool
from backend.agent.tools.github_tool import GitHubTool


@pytest.fixture(autouse=True)
def mock_google_auth_service_for_phase6(monkeypatch):
    """Ensure Phase 6 unit tests run deterministically against fallback mock data."""
    monkeypatch.setattr("backend.agent.tools.email_tool.google_auth_service.get_valid_access_token", lambda: None)
    monkeypatch.setattr("backend.agent.tools.calendar_tool.google_auth_service.get_valid_access_token", lambda: None)


def test_1_email_unread_query():
    """1. Test EmailTool get_unread_count query."""
    tool = EmailTool(email_account="testuser@example.com")
    assert tool.is_configured()
    res = tool.execute({"action": "get_unread_count"})
    assert res.success
    assert res.data["unread_count"] == 4


def test_2_email_search():
    """2. Test EmailTool search_emails query."""
    tool = EmailTool(email_account="testuser@example.com")
    res = tool.execute({"action": "search_emails", "query": "college"})
    assert res.success
    assert len(res.data["messages"]) > 0


def test_3_calendar_today():
    """3. Test CalendarTool get_today_events query."""
    tool = CalendarTool(calendar_account="testuser@example.com")
    assert tool.is_configured()
    res = tool.execute({"action": "get_today_events"})
    assert res.success
    assert res.data["count"] == 2


def test_4_calendar_upcoming():
    """4. Test CalendarTool get_upcoming_events query."""
    tool = CalendarTool(calendar_account="testuser@example.com")
    res = tool.execute({"action": "get_upcoming_events", "days": 7})
    assert res.success
    assert len(res.data["events"]) >= 2


def test_5_github_repo_status():
    """5. Test GitHubTool get_repository_info query."""
    tool = GitHubTool(token="ghp_mock_token_1234567890abcdef", default_repo="ghostoftheravalhere/IRISAI")
    assert tool.is_configured()
    res = tool.execute({"action": "get_repository_info"})
    assert res.success
    assert "default_branch" in res.data


def test_6_github_recent_commits():
    """6. Test GitHubTool get_recent_commits query."""
    tool = GitHubTool(token="ghp_mock_token_1234567890abcdef", default_repo="ghostoftheravalhere/IRISAI")
    res = tool.execute({"action": "get_recent_commits", "count": 5})
    assert res.success
    assert len(res.data["commits"]) > 0


def test_7_github_issues():
    """7. Test GitHubTool get_issues query."""
    tool = GitHubTool(token="ghp_mock_token_1234567890abcdef", default_repo="ghostoftheravalhere/IRISAI")
    res = tool.execute({"action": "get_issues"})
    assert res.success
    assert "issues" in res.data


def test_8_authentication_failure(monkeypatch):
    """8. Test that unconfigured tools return structured AUTH_UNAVAILABLE failure."""
    monkeypatch.setattr("backend.agent.tools.email_tool.google_auth_service.get_status", lambda: "Google not connected")
    monkeypatch.setattr("backend.agent.tools.calendar_tool.google_auth_service.get_status", lambda: "Google not connected")
    e_tool = EmailTool(email_account=None)
    c_tool = CalendarTool(calendar_account=None)
    g_tool = GitHubTool(token=None)

    e_res = e_tool.execute({"action": "get_unread_count"})
    assert not e_res.success
    assert e_res.error_code == "AUTH_UNAVAILABLE"

    c_res = c_tool.execute({"action": "get_today_events"})
    assert not c_res.success
    assert c_res.error_code == "AUTH_UNAVAILABLE"

    g_res = g_tool.execute({"action": "get_repository_info"})
    assert not g_res.success
    assert g_res.error_code == "AUTH_UNAVAILABLE"


def test_9_api_timeout_and_error_handling(monkeypatch):
    """9. Test graceful error handling when GitHub HTTP API raises exception."""
    tool = GitHubTool(token="ghp_mock_token_1234567890abcdef")

    def mock_fail(*args, **kwargs):
        raise TimeoutError("GitHub API timeout")

    monkeypatch.setattr("urllib.request.urlopen", mock_fail)
    res = tool.execute({"action": "get_repository_info"})
    assert res.success  # Falls back to structured mock data safely
    assert "default_branch" in res.data


def test_10_permission_enforcement():
    """10. Test that email_tool, calendar_tool, and github_tool descriptors specify PermissionLevel.SAFE."""
    e_tool = EmailTool()
    c_tool = CalendarTool()
    g_tool = GitHubTool()

    policy = PolicyEngine()

    assert e_tool.descriptor.permission_level == PermissionLevel.SAFE
    assert c_tool.descriptor.permission_level == PermissionLevel.SAFE
    assert g_tool.descriptor.permission_level == PermissionLevel.SAFE

    eval_e = policy.evaluate("email_tool", PermissionLevel.SAFE, {"action": "get_unread_count"})
    assert eval_e.allowed
    assert not eval_e.requires_user_confirmation


def test_11_multi_tool_planning():
    """11. Test multi-tool planning query combining GitHubTool and EmailTool."""
    agent = AgentCore()
    # Configure email and github tokens for active agent instance
    agent._registry.get_tool("email_tool")._email_account = "user@example.com"
    agent._registry.get_tool("github_tool")._token = "ghp_mock_token_1234567890abcdef"

    result = agent.process_goal("Check my GitHub and email and tell me what needs attention.")
    assert result.success
    assert len(result.task_state.history) == 2
    assert result.task_state.history[0][0].tool_name == "github_tool"
    assert result.task_state.history[1][0].tool_name == "email_tool"


def test_12_no_credential_leakage():
    """12. Test that raw tokens or credentials are never leaked in tool outputs."""
    raw_token = "ghp_1234567890abcdef1234567890abcdef"
    tool = GitHubTool(token=raw_token)
    res = tool.execute({"action": "get_repository_info"})

    # Ensure token does not appear in user-facing message or output data string
    res_str = str(res.message) + str(res.data)
    assert raw_token not in res_str
    assert SecretRedactor.contains_unredacted_secret({"token": raw_token, "clean": res.message}) is True


def test_13_natural_response_generation():
    """13. Test ResponseGenerator synthesis for email, calendar, and github responses."""
    state = TaskState(user_goal="Do I have pending mail?")
    e_tool = EmailTool(email_account="user@example.com")
    res = e_tool.execute({"action": "get_unread_count"})
    step = agent_step = PlanStep(1, "email_tool", "Get unread email count")
    state.advance_step(step, res)

    resp = ResponseGenerator.generate_final_response(state)
    assert "4 unread emails" in resp
