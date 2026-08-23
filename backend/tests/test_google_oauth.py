"""Test suite for Google OAuth 2.0 Account Integration, secure token storage, and tool readiness."""

import json
import os
import tempfile
import pytest

from backend.agent.tools.calendar_tool import CalendarTool
from backend.agent.tools.email_tool import EmailTool
from backend.auth.google_auth_service import GoogleAuthService, GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE


@pytest.fixture
def temp_auth_service():
    with tempfile.NamedTemporaryFile(suffix=".enc", delete=False) as tf:
        storage_path = tf.name
    
    auth_service = GoogleAuthService(
        client_id="test_client_id_123",
        client_secret="test_client_secret_456",
        redirect_uri="http://localhost:8000/api/auth/google/callback",
        storage_path=storage_path,
    )
    yield auth_service
    
    if os.path.exists(storage_path):
        try:
            os.remove(storage_path)
        except Exception:
            pass


def test_oauth_start(temp_auth_service):
    """1. Test OAuth initialization and authorization URL construction with read-only scopes."""
    auth_url = temp_auth_service.get_authorization_url(state="test_state")
    assert "https://accounts.google.com/o/oauth2/v2/auth" in auth_url
    assert "client_id=test_client_id_123" in auth_url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fauth%2Fgoogle%2Fcallback" in auth_url
    assert "gmail.readonly" in auth_url
    assert "calendar.readonly" in auth_url
    assert "access_type=offline" in auth_url


def test_oauth_callback(temp_auth_service, monkeypatch):
    """2. Test OAuth callback code exchange, actual email resolution, and token storage."""
    monkeypatch.setattr(temp_auth_service, "_fetch_user_email", lambda token: "test@example.com")
    tokens = temp_auth_service.exchange_code_for_tokens("auth_code_xyz")
    assert "access_token" in tokens
    assert temp_auth_service.get_status() == "Google connected"
    assert temp_auth_service.get_account_email() == "test@example.com"
    assert temp_auth_service.get_account_email() != "user@gmail.com"


def test_account_identity_display_and_no_placeholder(temp_auth_service, monkeypatch):
    """Test authenticated email identity resolution and fallback without placeholder user@gmail.com."""
    from fastapi.testclient import TestClient
    from backend.api.app import create_app

    monkeypatch.setattr("backend.api.routes.auth_routes.google_auth_service", temp_auth_service)
    
    # 1. With actual authenticated email test@example.com
    temp_auth_service.save_tokens(
        access_token="tok_123",
        refresh_token="ref_123",
        expires_in=3600,
        account_email="test@example.com",
    )
    
    assert temp_auth_service.get_account_email() == "test@example.com"
    
    app = create_app()
    client = TestClient(app)
    
    status_resp = client.get("/api/auth/google/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["account_email"] == "test@example.com"
    assert status_resp.json()["account_email"] != "user@gmail.com"
    
    # 2. Unresolvable email fallback test
    temp_auth_service.clear_credentials()
    temp_auth_service.save_tokens(
        access_token="tok_456",
        refresh_token="ref_456",
        expires_in=3600,
        account_email=None,
    )
    monkeypatch.setattr(temp_auth_service, "_fetch_user_email", lambda token: None)
    
    assert temp_auth_service.get_account_email() is None
    status_resp_none = client.get("/api/auth/google/status")
    assert status_resp_none.json()["account_email"] is None
    assert status_resp_none.json()["account_email"] != "user@gmail.com"


def test_successful_credential_storage(temp_auth_service):
    """3. Test secure credential encryption and retrieval without plaintext file exposure."""
    temp_auth_service.save_tokens(
        access_token="secret_access_token_123",
        refresh_token="secret_refresh_token_456",
        expires_in=3600,
        account_email="testuser@domain.com",
    )
    
    # Raw file should not contain plaintext secret string
    with open(temp_auth_service._storage_path, "r", encoding="utf-8") as f:
        raw_content = f.read()
    assert "secret_access_token_123" not in raw_content
    
    # Decrypted structure should contain credentials
    loaded = temp_auth_service.load_credentials()
    assert loaded is not None
    assert loaded["access_token"] == "secret_access_token_123"
    assert loaded["refresh_token"] == "secret_refresh_token_456"
    assert loaded["account_email"] == "testuser@domain.com"


def test_expired_credential(temp_auth_service):
    """4. Test automatic access token refresh on token expiration."""
    # Save token expired 10 minutes ago
    temp_auth_service.save_tokens(
        access_token="expired_token_789",
        refresh_token="valid_refresh_token_000",
        expires_in=-600,
        account_email="expired@domain.com",
    )
    
    valid_token = temp_auth_service.get_valid_access_token()
    assert valid_token is not None
    assert valid_token != "expired_token_789"
    assert "refreshed_access_token" in valid_token or "mock_access_token" in valid_token


def test_authentication_failure(temp_auth_service):
    """5. Test unconfigured status and authentication clearing/failure handling."""
    assert temp_auth_service.get_status() == "Google not connected"
    assert temp_auth_service.get_valid_access_token() is None
    
    temp_auth_service.save_tokens(access_token="tok", expires_in=3600)
    assert temp_auth_service.get_status() == "Google connected"
    
    temp_auth_service.clear_credentials()
    assert temp_auth_service.get_status() == "Google not connected"


def test_gmail_read_only_access(temp_auth_service, monkeypatch):
    """6. Test EmailTool connected vs unconfigured read-only execution."""
    monkeypatch.setattr("backend.agent.tools.email_tool.google_auth_service", temp_auth_service)
    
    tool = EmailTool()
    
    # Unconfigured state
    assert tool.is_configured() is False
    unconfig_res = tool.execute({"action": "get_unread_count"})
    assert unconfig_res.success is False
    assert unconfig_res.error_code == "AUTH_UNAVAILABLE"
    
    # Connected state
    temp_auth_service.save_tokens(access_token="valid_gmail_token", expires_in=3600, account_email="student@university.edu")
    assert tool.is_configured() is True
    
    res = tool.execute({"action": "get_unread_count"})
    assert res.success is True
    assert res.data["unread_count"] == 4
    assert res.data["account"] == "student@university.edu"


def test_calendar_read_only_access(temp_auth_service, monkeypatch):
    """7. Test CalendarTool connected vs unconfigured read-only execution."""
    monkeypatch.setattr("backend.agent.tools.calendar_tool.google_auth_service", temp_auth_service)
    
    tool = CalendarTool()
    
    # Unconfigured state
    assert tool.is_configured() is False
    unconfig_res = tool.execute({"action": "get_today_events"})
    assert unconfig_res.success is False
    assert unconfig_res.error_code == "AUTH_UNAVAILABLE"
    
    # Connected state
    temp_auth_service.save_tokens(access_token="valid_calendar_token", expires_in=3600, account_email="student@university.edu")
    assert tool.is_configured() is True
    
    res = tool.execute({"action": "get_today_events"})
    assert res.success is True
    assert res.data["count"] > 0
    
    next_res = tool.execute({"action": "get_next_event"})
    assert next_res.success is True
    assert "next_event" in next_res.data


def test_token_redaction(temp_auth_service):
    """8. Test secret token redaction in logs and structured payloads."""
    payload = {
        "user": "test_user",
        "access_token": "secret_abc_123",
        "client_secret": "secret_def_456",
        "nested": {"authorization_code": "secret_code_789"},
    }
    
    sanitized = temp_auth_service.sanitize_log_data(payload)
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["client_secret"] == "[REDACTED]"
    assert sanitized["nested"]["authorization_code"] == "[REDACTED]"
    assert sanitized["user"] == "test_user"


def test_no_credential_leakage_in_tool_results(temp_auth_service, monkeypatch):
    """9. Test zero token leakage in EmailTool and CalendarTool execution results."""
    monkeypatch.setattr("backend.agent.tools.email_tool.google_auth_service", temp_auth_service)
    monkeypatch.setattr("backend.agent.tools.calendar_tool.google_auth_service", temp_auth_service)
    
    temp_auth_service.save_tokens(access_token="sensitive_access_token_999", expires_in=3600)
    
    email_tool = EmailTool()
    cal_tool = CalendarTool()
    
    res_e = email_tool.execute({"action": "get_important_unread"})
    res_c = cal_tool.execute({"action": "get_upcoming_events"})
    
    str_e = json.dumps(res_e.data)
    str_c = json.dumps(res_c.data)
    
    assert "sensitive_access_token_999" not in str_e
    assert "sensitive_access_token_999" not in str_c
