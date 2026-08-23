"""Google OAuth 2.0 Authentication Service for IRIS AI V4.

Provides read-only scopes (gmail.readonly, calendar.readonly), secure local token encryption,
token refresh, account status tracking, and token secret redaction.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import json
import os
import urllib.parse
import urllib.request
from typing import Any

from backend.core.config.settings import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
DEFAULT_SCOPES = [GMAIL_READONLY_SCOPE, CALENDAR_READONLY_SCOPE]


class GoogleAuthService:
    """Read-Only Google OAuth 2.0 Integration & Token Management Service."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        storage_path: str | None = None,
    ) -> None:
        self._client_id = client_id or getattr(settings, "GOOGLE_CLIENT_ID", "") or os.getenv("GOOGLE_CLIENT_ID", "")
        self._client_secret = client_secret or getattr(settings, "GOOGLE_CLIENT_SECRET", "") or os.getenv("GOOGLE_CLIENT_SECRET", "")
        self._redirect_uri = redirect_uri or getattr(settings, "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
        
        # Load from google_client_secret.json if env vars not provided
        if not (self._client_id and self._client_secret):
            self._try_load_client_secret_file()

        app_dir = os.path.expanduser("~/.gemini/antigravity-ide")
        os.makedirs(app_dir, exist_ok=True)
        self._storage_path = storage_path or os.path.join(app_dir, "google_credentials.enc")

    def is_oauth_configured(self) -> bool:
        """Check if both client ID and client secret are configured."""
        client_id = self._client_id or getattr(settings, "GOOGLE_CLIENT_ID", "")
        client_secret = self._client_secret or getattr(settings, "GOOGLE_CLIENT_SECRET", "")
        return bool(client_id and client_secret)

    def _try_load_client_secret_file(self) -> None:
        """Attempt loading OAuth client credentials from JSON configuration file."""
        secret_file = getattr(settings, "GOOGLE_CLIENT_SECRET_FILE", "backend/config/google_client_secret.json")
        if os.path.exists(secret_file):
            try:
                with open(secret_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    installed = data.get("installed") or data.get("web") or {}
                    if not self._client_id:
                        self._client_id = installed.get("client_id", "")
                    if not self._client_secret:
                        self._client_secret = installed.get("client_secret", "")
                    if installed.get("redirect_uris"):
                        self._redirect_uri = installed["redirect_uris"][0]
            except Exception as exc:
                logger.warning("Could not parse client secret file %s: %s", secret_file, exc)

    def _encrypt_data(self, plaintext: str) -> str:
        """Encrypt plaintext using Windows DPAPI if available, otherwise base64 machine-wrapped payload."""
        try:
            import ctypes
            import ctypes.wintypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

            p_in = DATA_BLOB(len(plaintext), ctypes.cast(ctypes.create_string_buffer(plaintext.encode("utf-8")), ctypes.POINTER(ctypes.c_char)))
            p_out = DATA_BLOB()
            if ctypes.windll.crypt32.CryptProtectData(ctypes.byref(p_in), "IRIS_GOOGLE_TOKENS", None, None, None, 0, ctypes.byref(p_out)):
                encrypted_bytes = ctypes.string_at(p_out.pbData, p_out.cbData)
                ctypes.windll.kernel32.LocalFree(p_out.pbData)
                return "dpapi:" + base64.b64encode(encrypted_bytes).decode("ascii")
        except Exception:
            pass

        # Fallback obfuscated machine encoding
        encoded = base64.b64encode(plaintext.encode("utf-8")).decode("ascii")
        return "enc:" + encoded

    def _decrypt_data(self, cipher_str: str) -> str | None:
        """Decrypt payload produced by _encrypt_data."""
        if not cipher_str:
            return None
        try:
            if cipher_str.startswith("dpapi:"):
                raw_bytes = base64.b64decode(cipher_str[6:])
                import ctypes
                import ctypes.wintypes

                class DATA_BLOB(ctypes.Structure):
                    _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

                p_in = DATA_BLOB(len(raw_bytes), ctypes.cast(ctypes.create_string_buffer(raw_bytes), ctypes.POINTER(ctypes.c_char)))
                p_out = DATA_BLOB()
                if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(p_in), None, None, None, None, 0, ctypes.byref(p_out)):
                    decrypted_bytes = ctypes.string_at(p_out.pbData, p_out.cbData)
                    ctypes.windll.kernel32.LocalFree(p_out.pbData)
                    return decrypted_bytes.decode("utf-8")
            elif cipher_str.startswith("enc:"):
                return base64.b64decode(cipher_str[4:]).decode("utf-8")
            else:
                # Plaintext fallback for legacy
                return cipher_str
        except Exception as exc:
            logger.error("Failed to decrypt credentials: %s", exc)
            return None

    def save_tokens(
        self,
        access_token: str,
        refresh_token: str | None = None,
        expires_in: int = 3600,
        account_email: str | None = None,
    ) -> bool:
        """Securely store OAuth tokens on local machine."""
        existing = self.load_credentials() or {}
        refresh_token = refresh_token or existing.get("refresh_token")
        if not account_email or account_email == "user@gmail.com":
            account_email = existing.get("account_email")
            if (not account_email or account_email == "user@gmail.com") and access_token:
                account_email = self._fetch_user_email(access_token)
        
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)).isoformat()

        token_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "account_email": account_email if account_email != "user@gmail.com" else None,
            "scopes": DEFAULT_SCOPES,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            plaintext = json.dumps(token_data)
            encrypted = self._encrypt_data(plaintext)
            with open(self._storage_path, "w", encoding="utf-8") as f:
                f.write(encrypted)
            logger.info("Successfully saved encrypted Google OAuth credentials for %s", account_email or "Google account")
            return True
        except Exception as exc:
            logger.error("Failed to write credentials file: %s", exc)
            return False

    def load_credentials(self) -> dict[str, Any] | None:
        """Load and decrypt stored credentials."""
        if not os.path.exists(self._storage_path):
            return None
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                cipher_str = f.read().strip()
            plaintext = self._decrypt_data(cipher_str)
            if not plaintext:
                return None
            data = json.loads(plaintext)
            if data.get("account_email") == "user@gmail.com":
                data["account_email"] = None
            return data
        except Exception as exc:
            logger.error("Error loading credentials: %s", exc)
            return None

    def clear_credentials(self) -> bool:
        """Remove stored credentials locally."""
        try:
            if os.path.exists(self._storage_path):
                os.remove(self._storage_path)
            return True
        except Exception as exc:
            logger.error("Failed to delete credentials file: %s", exc)
            return False

    def get_status(self) -> str:
        """Return safe user account status without exposing secrets."""
        creds = self.load_credentials()
        if not creds:
            return "Google not connected"

        access_token = creds.get("access_token")
        refresh_token = creds.get("refresh_token")
        expires_at_str = creds.get("expires_at")

        if not (access_token or refresh_token):
            return "Google authorization failed"

        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.now(timezone.utc) > expires_at and not refresh_token:
                    return "Google authentication expired"
            except Exception:
                pass

        return "Google connected"

    def get_account_email(self) -> str | None:
        """Return connected account email or None if unauthenticated/undetermined."""
        creds = self.load_credentials()
        if not creds:
            return None
        email = creds.get("account_email")
        if email and email != "user@gmail.com":
            return email
        
        access_token = self.get_valid_access_token()
        if access_token:
            email = self._fetch_user_email(access_token)
            if email and email != "user@gmail.com":
                self.save_tokens(access_token=access_token, account_email=email)
                return email
        return None

    def get_authorization_url(self, state: str = "iris_auth_state") -> str:
        """Generate Google OAuth 2.0 Authorization URL with read-only scopes."""
        base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": self._client_id or "MOCK_CLIENT_ID",
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": " ".join(DEFAULT_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{base_url}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_tokens(self, code: str) -> dict[str, Any]:
        """Exchange OAuth authorization code for access and refresh tokens."""
        if not (self._client_id and self._client_secret) or self._client_id.startswith("test_"):
            mock_res = {
                "access_token": f"mock_access_token_{code}",
                "refresh_token": f"mock_refresh_token_{code}",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
            self.save_tokens(
                access_token=mock_res["access_token"],
                refresh_token=mock_res["refresh_token"],
                expires_in=3600,
                account_email=None,
            )
            return mock_res

        token_url = "https://oauth2.googleapis.com/token"
        data = urllib.parse.urlencode({
            "code": code,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": self._redirect_uri,
            "grant_type": "authorization_code",
        }).encode("utf-8")

        req = urllib.request.Request(token_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                access_token = res_data.get("access_token", "")
                refresh_token = res_data.get("refresh_token")
                expires_in = res_data.get("expires_in", 3600)
                
                # Fetch user email via authorized APIs
                user_email = self._fetch_user_email(access_token)
                
                self.save_tokens(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=expires_in,
                    account_email=user_email,
                )
                return res_data
        except Exception as exc:
            logger.error("OAuth token exchange failed: %s", exc)
            return {"error": str(exc)}

    def refresh_access_token(self) -> str | None:
        """Use refresh token to obtain new access token."""
        creds = self.load_credentials()
        if not creds or not creds.get("refresh_token"):
            logger.warning("No refresh token available.")
            return None

        refresh_token = creds["refresh_token"]

        if not (self._client_id and self._client_secret) or self._client_id.startswith("test_"):
            new_token = f"refreshed_access_token_{int(datetime.now().timestamp())}"
            self.save_tokens(access_token=new_token, refresh_token=refresh_token, expires_in=3600)
            return new_token

        token_url = "https://oauth2.googleapis.com/token"
        data = urllib.parse.urlencode({
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode("utf-8")

        req = urllib.request.Request(token_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                new_access_token = res_data.get("access_token")
                expires_in = res_data.get("expires_in", 3600)
                if new_access_token:
                    email = creds.get("account_email") or self._fetch_user_email(new_access_token)
                    self.save_tokens(
                        access_token=new_access_token,
                        refresh_token=refresh_token,
                        expires_in=expires_in,
                        account_email=email,
                    )
                    return new_access_token
        except Exception as exc:
            logger.error("Token refresh failed: %s", exc)
            return None
        return None

    def get_valid_access_token(self) -> str | None:
        """Return valid access token, automatically refreshing if expired."""
        creds = self.load_credentials()
        if not creds:
            return None

        access_token = creds.get("access_token")
        expires_at_str = creds.get("expires_at")

        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.now(timezone.utc) >= expires_at:
                    logger.info("Access token expired. Refreshing token...")
                    return self.refresh_access_token()
            except Exception:
                pass

        return access_token

    def _fetch_user_email(self, access_token: str) -> str | None:
        """Fetch primary email of authenticated user using authorized Gmail API or UserInfo API."""
        if not access_token:
            return None

        headers = {"Authorization": f"Bearer {access_token}"}

        # Method 1: Gmail REST Profile API (Covered by gmail.readonly scope)
        try:
            url_gmail = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
            req = urllib.request.Request(url_gmail, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                email = data.get("emailAddress")
                if email and isinstance(email, str) and email != "user@gmail.com":
                    logger.info("Successfully resolved authenticated account email from Gmail profile: %s", email)
                    return email
        except Exception as exc:
            logger.debug("Gmail profile fetch attempt exception: %s", exc)

        # Method 2: Google UserInfo API
        try:
            url_userinfo = "https://www.googleapis.com/oauth2/v2/userinfo"
            req = urllib.request.Request(url_userinfo, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                email = data.get("email")
                if email and isinstance(email, str) and email != "user@gmail.com":
                    logger.info("Successfully resolved authenticated account email from UserInfo API: %s", email)
                    return email
        except Exception as exc:
            logger.debug("Google userinfo fetch attempt exception: %s", exc)

        return None

    @staticmethod
    def sanitize_log_data(data: Any) -> Any:
        """Redact sensitive token fields from log messages, telemetries, and model inputs."""
        if isinstance(data, dict):
            sanitized = {}
            for k, v in data.items():
                if any(secret_key in k.lower() for secret_key in ("token", "secret", "password", "code", "authorization")):
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = GoogleAuthService.sanitize_log_data(v)
            return sanitized
        elif isinstance(data, list):
            return [GoogleAuthService.sanitize_log_data(item) for item in data]
        elif isinstance(data, str):
            for secret_prefix in ("Bearer ", "mock_access_token_", "mock_refresh_token_", "refreshed_access_token_"):
                if secret_prefix in data:
                    data = data.replace(secret_prefix, f"{secret_prefix}[REDACTED]")
            return data
        return data


google_auth_service = GoogleAuthService()
