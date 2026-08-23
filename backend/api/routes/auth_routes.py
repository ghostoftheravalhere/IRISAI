"""Google OAuth 2.0 API routes for IRIS AI V4.

Provides OAuth login initiation, callback handler, safe account status querying, and disconnect endpoint.
"""

from __future__ import annotations

import webbrowser

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from backend.auth.google_auth_service import DEFAULT_SCOPES, google_auth_service

router = APIRouter(prefix="/api/auth/google", tags=["google-auth"])


@router.get("/login")
def start_google_oauth(open_browser: bool = True):
    """Start Google OAuth 2.0 login flow with read-only scopes."""
    if not google_auth_service.is_oauth_configured():
        raise HTTPException(
            status_code=400,
            detail="Google Client Secret is missing in configuration (.env). Please paste your GOOGLE_CLIENT_SECRET in .env to enable OAuth authorization.",
        )
    auth_url = google_auth_service.get_authorization_url()
    if open_browser:
        try:
            webbrowser.open(auth_url)
        except Exception:
            pass
    return {
        "status": "OAuth authorization flow started in browser",
        "auth_url": auth_url,
        "scopes": DEFAULT_SCOPES,
    }


@router.get("/callback", response_class=HTMLResponse)
def handle_google_oauth_callback(
    code: str = Query(None, description="Authorization code from Google"),
    error: str = Query(None, description="Error returned by Google OAuth"),
):
    """Handle OAuth 2.0 callback from Google."""
    if error:
        html_error = f"""
        <!DOCTYPE html>
        <html>
        <head><title>IRIS AI - Authorization Failed</title></head>
        <body style="font-family: system-ui, sans-serif; text-align: center; padding-top: 50px; background: #0f172a; color: #f8fafc;">
            <h1 style="color: #ef4444;">Google Authorization Failed</h1>
            <p>Error details: {error}</p>
            <p>You may close this tab and try again in IRIS AI.</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html_error, status_code=400)

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    res = google_auth_service.exchange_code_for_tokens(code)
    if "error" in res:
        html_fail = f"""
        <!DOCTYPE html>
        <html>
        <head><title>IRIS AI - Connection Error</title></head>
        <body style="font-family: system-ui, sans-serif; text-align: center; padding-top: 50px; background: #0f172a; color: #f8fafc;">
            <h1 style="color: #f59e0b;">Google Token Exchange Failed</h1>
            <p>{res['error']}</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html_fail, status_code=500)

    account_email = google_auth_service.get_account_email() or "your Google account"

    html_success = f"""
    <!DOCTYPE html>
    <html>
    <head><title>IRIS AI - Google Connected</title></head>
    <body style="font-family: system-ui, sans-serif; text-align: center; padding-top: 50px; background: #0f172a; color: #f8fafc;">
        <h1 style="color: #10b981;">✓ Google Account Connected</h1>
        <p style="font-size: 1.2rem; color: #94a3b8;">Successfully connected <strong>{account_email}</strong> to IRIS AI.</p>
        <p style="color: #64748b;">Read-only Gmail & Calendar permissions active. You can now close this tab.</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html_success, status_code=200)


@router.get("/status")
def get_google_account_status():
    """Get safe account status without exposing tokens or secrets."""
    status_str = google_auth_service.get_status()
    email = google_auth_service.get_account_email()
    return {
        "status": status_str,
        "is_connected": status_str == "Google connected",
        "account_email": email if status_str == "Google connected" else None,
        "scopes": DEFAULT_SCOPES,
    }


@router.post("/disconnect")
def disconnect_google_account():
    """Revoke and remove local encrypted Google OAuth credentials."""
    success = google_auth_service.clear_credentials()
    return {
        "status": "Google disconnected" if success else "Failed to disconnect",
        "is_connected": False,
    }


# GitHub Authentication Endpoints
from backend.auth.github_auth_service import github_auth_service
from pydantic import BaseModel

github_router = APIRouter(prefix="/api/auth/github", tags=["github-auth"])


class GitHubConnectPayload(BaseModel):
    token: str
    default_repo: str | None = None


@github_router.get("/status")
def get_github_account_status():
    """Get safe GitHub account status without exposing tokens."""
    status_str = github_auth_service.get_status()
    username = github_auth_service.get_account_username()
    default_repo = github_auth_service.get_default_repo()
    return {
        "status": status_str,
        "is_connected": status_str == "GitHub connected",
        "username": username if status_str == "GitHub connected" else None,
        "default_repo": default_repo,
    }


@github_router.post("/connect")
def connect_github_account(payload: GitHubConnectPayload):
    """Securely store encrypted GitHub Personal Access Token."""
    token = payload.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token string cannot be empty")

    success = github_auth_service.save_token(token, default_repo=payload.default_repo)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to connect GitHub account. Check token format.")

    username = github_auth_service.get_account_username()
    return {
        "status": "GitHub connected",
        "is_connected": True,
        "username": username,
        "default_repo": github_auth_service.get_default_repo(),
    }


@github_router.post("/disconnect")
def disconnect_github_account():
    """Revoke and remove local encrypted GitHub credentials."""
    success = github_auth_service.clear_credentials()
    return {
        "status": "GitHub disconnected" if success else "Failed to disconnect",
        "is_connected": False,
    }
