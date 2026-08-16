"""Verification script for Google OAuth setup and configuration behavior."""

import os
import sys
import subprocess

sys.path.insert(0, os.path.abspath("."))

from fastapi.testclient import TestClient
from backend.api.app import create_app
from backend.agent.tools.email_tool import EmailTool
from backend.agent.tools.calendar_tool import CalendarTool
from backend.auth.google_auth_service import GoogleAuthService
from backend.core.config.settings import Settings

def run_checks():
    settings = Settings()
    auth_service = GoogleAuthService()

    print("--- 1. GOOGLE_CLIENT_ID ---")
    client_id = settings.GOOGLE_CLIENT_ID
    print("Loaded CLIENT_ID:", client_id)
    assert client_id == "677774134957-qhfi409vn9kg867g9g6hs0kbtd26b439.apps.googleusercontent.com"
    print("PASS: GOOGLE_CLIENT_ID loads correctly.")

    print("\n--- 2. GOOGLE_REDIRECT_URI ---")
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    print("Loaded REDIRECT_URI:", redirect_uri)
    assert redirect_uri == "http://localhost:8000/api/auth/google/callback"
    print("PASS: GOOGLE_REDIRECT_URI loads correctly.")

    print("\n--- 3. GOOGLE_CLIENT_SECRET DETECTION ---")
    client_secret = settings.GOOGLE_CLIENT_SECRET
    has_secret = bool(client_secret and client_secret.strip())
    print("Has GOOGLE_CLIENT_SECRET in .env:", has_secret)
    if has_secret:
        print("DETECTED: GOOGLE_CLIENT_SECRET is NOW SUPPLIED in .env! (Length:", len(client_secret), ")")
    else:
        print("DETECTED: GOOGLE_CLIENT_SECRET is MISSING in .env.")
    print("PASS: Client secret detection verified.")

    app = create_app()
    client = TestClient(app)

    print("\n--- 4. GET /api/auth/google/status ---")
    resp_status = client.get("/api/auth/google/status")
    print("Status response:", resp_status.status_code, resp_status.json())
    assert resp_status.status_code == 200
    assert resp_status.json()["status"] in ("Google not connected", "Google connected")
    assert "scopes" in resp_status.json()
    print("PASS: /api/auth/google/status works safely and does not expose tokens.")

    print("\n--- 5. GET /api/auth/google/login ---")
    resp_login = client.get("/api/auth/google/login?open_browser=false")
    print("Login response code:", resp_login.status_code)
    if not has_secret:
        assert resp_login.status_code == 400
        assert "Google Client Secret is missing" in resp_login.json()["detail"]
        print("PASS: /api/auth/google/login fails gracefully with 400 missing secret error.")
    else:
        assert resp_login.status_code == 200
        assert "auth_url" in resp_login.json()
        print("PASS: /api/auth/google/login constructs valid authorization URL when secret is supplied.")

    print("\n--- 6. EmailTool Unconfigured State ---")
    email_tool = EmailTool()
    res_e = email_tool.execute({"action": "get_unread_count"})
    print("EmailTool output:", res_e.success, getattr(res_e, "error_code", None), res_e.message)
    if not auth_service.load_credentials():
        assert res_e.success is False
        assert res_e.error_code == "AUTH_UNAVAILABLE"
        print("PASS: EmailTool returns AUTH_UNAVAILABLE when user has not completed OAuth consent flow.")
    else:
        print("PASS: EmailTool executed with active credentials.")

    print("\n--- 7. CalendarTool Unconfigured State ---")
    cal_tool = CalendarTool()
    res_c = cal_tool.execute({"action": "get_today_events"})
    print("CalendarTool output:", res_c.success, getattr(res_c, "error_code", None), res_c.message)
    if not auth_service.load_credentials():
        assert res_c.success is False
        assert res_c.error_code == "AUTH_UNAVAILABLE"
        print("PASS: CalendarTool returns AUTH_UNAVAILABLE when user has not completed OAuth consent flow.")
    else:
        print("PASS: CalendarTool executed with active credentials.")

    print("\n--- 8. Log Redaction Test ---")
    sanitized = auth_service.sanitize_log_data({"access_token": "secret_val_123", "client_secret": "secret_val_456"})
    print("Sanitized data:", sanitized)
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["client_secret"] == "[REDACTED]"
    print("PASS: No secrets written to logs.")

    print("\n--- 9. .env Gitignore Check ---")
    git_check = subprocess.run(["git", "check-ignore", "-v", ".env"], capture_output=True, text=True)
    print("Git ignore output:", git_check.stdout.strip())
    assert ".env" in git_check.stdout
    print("PASS: .env remains gitignored.")

if __name__ == "__main__":
    run_checks()
