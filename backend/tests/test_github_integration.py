"""Test suite for Real GitHub Account Integration, DPAPI token storage, and multi-service planning."""

import json
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.agent.planner import Planner
from backend.agent.tools.calendar_tool import CalendarTool
from backend.agent.tools.email_tool import EmailTool
from backend.agent.tools.github_tool import GitHubTool
from backend.auth.github_auth_service import GitHubAuthService


@pytest.fixture
def temp_github_service():
    with tempfile.NamedTemporaryFile(suffix=".enc", delete=False) as tf:
        storage_path = tf.name
    
    auth_service = GitHubAuthService(
        token="ghp_test_token_1234567890abcdef",
        default_repo="ghostoftheravalhere/IRISAI",
        storage_path=storage_path,
    )
    yield auth_service
    
    if os.path.exists(storage_path):
        try:
            os.remove(storage_path)
        except Exception:
            pass


def test_1_github_auth_storage(temp_github_service):
    """1. Test GitHub DPAPI token encryption and retrieval without plaintext exposure."""
    temp_github_service.save_token("ghp_secret_access_token_999", username="testuser", default_repo="owner/repo")
    
    # Raw file should not contain plaintext token
    with open(temp_github_service._storage_path, "r", encoding="utf-8") as f:
        raw_content = f.read()
    assert "ghp_secret_access_token_999" not in raw_content
    
    # Decrypted credentials should contain details
    loaded = temp_github_service.load_credentials()
    assert loaded is not None
    assert loaded["token"] == "ghp_secret_access_token_999"
    assert loaded["username"] == "testuser"
    assert loaded["default_repo"] == "owner/repo"


def test_2_connection_status(temp_github_service, monkeypatch):
    """2. Test safe account status API endpoint without exposing secrets."""
    monkeypatch.setattr("backend.api.routes.auth_routes.github_auth_service", temp_github_service)
    
    app = create_app()
    client = TestClient(app)
    
    # Unconfigured state
    temp_github_service.clear_credentials()
    monkeypatch.setattr(temp_github_service, "_token_env", "")
    status_resp = client.get("/api/auth/github/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["is_connected"] is False
    assert status_resp.json()["username"] is None
    
    # Connected state
    temp_github_service.save_token("ghp_valid_token_123", username="testuser")
    status_connected = client.get("/api/auth/github/status")
    assert status_connected.status_code == 200
    assert status_connected.json()["is_connected"] is True
    assert status_connected.json()["username"] == "testuser"
    assert "ghp_" not in json.dumps(status_connected.json())


def test_3_repo_information_query(temp_github_service, monkeypatch):
    """3. Test GitHubTool get_repository_info query."""
    monkeypatch.setattr("backend.agent.tools.github_tool.github_auth_service", temp_github_service)
    temp_github_service.save_token("ghp_valid_token_123", username="testuser")
    
    tool = GitHubTool()
    assert tool.is_configured() is True
    
    res = tool.execute({"action": "get_repository_info", "repo": "owner/testrepo"})
    assert res.success is True
    assert "testrepo" in json.dumps(res.data) or "default_branch" in res.data


def test_4_recent_commits_query(temp_github_service, monkeypatch):
    """4. Test GitHubTool get_recent_commits query."""
    monkeypatch.setattr("backend.agent.tools.github_tool.github_auth_service", temp_github_service)
    temp_github_service.save_token("ghp_valid_token_123", username="testuser")
    
    tool = GitHubTool()
    res = tool.execute({"action": "get_recent_commits", "count": 3})
    assert res.success is True
    assert "commits" in res.data


def test_5_issues_query(temp_github_service, monkeypatch):
    """5. Test GitHubTool get_issues query."""
    monkeypatch.setattr("backend.agent.tools.github_tool.github_auth_service", temp_github_service)
    temp_github_service.save_token("ghp_valid_token_123", username="testuser")
    
    tool = GitHubTool()
    res = tool.execute({"action": "get_issues", "state": "open"})
    assert res.success is True
    assert "issues" in res.data


def test_6_pull_requests_query(temp_github_service, monkeypatch):
    """6. Test GitHubTool get_pull_requests query."""
    monkeypatch.setattr("backend.agent.tools.github_tool.github_auth_service", temp_github_service)
    temp_github_service.save_token("ghp_valid_token_123", username="testuser")
    
    tool = GitHubTool()
    res = tool.execute({"action": "get_pull_requests", "state": "open"})
    assert res.success is True
    assert "pull_requests" in res.data


def test_7_workflow_status_query(temp_github_service, monkeypatch):
    """7. Test GitHubTool get_workflow_status query."""
    monkeypatch.setattr("backend.agent.tools.github_tool.github_auth_service", temp_github_service)
    temp_github_service.save_token("ghp_valid_token_123", username="testuser")
    
    tool = GitHubTool()
    res = tool.execute({"action": "get_workflow_status"})
    assert res.success is True
    assert "workflow_status" in res.data


def test_8_auth_failure_handling(temp_github_service, monkeypatch):
    """8. Test structured AUTH_UNAVAILABLE returned when unconfigured."""
    monkeypatch.setattr("backend.agent.tools.github_tool.github_auth_service", temp_github_service)
    temp_github_service.clear_credentials()
    monkeypatch.setattr(temp_github_service, "_token_env", "")
    
    tool = GitHubTool()
    assert tool.is_configured() is False
    
    res = tool.execute({"action": "get_repository_info"})
    assert res.success is False
    assert res.error_code == "AUTH_UNAVAILABLE"


def test_9_token_redaction(temp_github_service):
    """9. Test secret token redaction in logs and structured dicts."""
    payload = {
        "user": "testuser",
        "github_token": "ghp_secret_key_1234567890",
        "authorization": "Bearer ghp_secret_key_1234567890",
    }
    sanitized = temp_github_service.sanitize_log_data(payload)
    assert sanitized["github_token"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["user"] == "testuser"


def test_10_multi_service_planning():
    """10. Test multi-service 3-tool planning for Email + Calendar + GitHub query."""
    planner = Planner()
    available_tools = [EmailTool().descriptor, CalendarTool().descriptor, GitHubTool().descriptor]
    
    goal = "IRIS, check my email, calendar, and GitHub and tell me what needs my attention."
    plan = planner.create_plan(goal, available_tools)
    
    assert len(plan.steps) >= 3
    tool_names = [step.tool_name for step in plan.steps]
    assert "email_tool" in tool_names
    assert "calendar_tool" in tool_names
    assert "github_tool" in tool_names
