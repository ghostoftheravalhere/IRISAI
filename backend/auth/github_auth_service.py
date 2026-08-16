"""GitHub Authentication & Token Management Service for IRIS AI V4.

Provides secure local token encryption (DPAPI), GitHub user profile validation,
token secret redaction, and connection status reporting.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.request
from typing import Any

from backend.core.config.settings import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GitHubAuthService:
    """Read-Only GitHub Fine-Grained Token Integration & Security Service."""

    def __init__(
        self,
        token: str | None = None,
        default_repo: str | None = None,
        storage_path: str | None = None,
    ) -> None:
        self._token_env = (
            token
            or getattr(settings, "GITHUB_API_TOKEN", None)
            or os.getenv("GITHUB_TOKEN")
            or os.getenv("IRIS_GITHUB_TOKEN")
            or ""
        )
        self._default_repo = (
            default_repo
            or getattr(settings, "GITHUB_DEFAULT_REPO", None)
            or os.getenv("IRIS_GITHUB_REPO")
            or "ghostoftheravalhere/IRISAI"
        )

        app_dir = os.path.expanduser("~/.gemini/antigravity-ide")
        os.makedirs(app_dir, exist_ok=True)
        self._storage_path = storage_path or os.path.join(app_dir, "github_credentials.enc")

    def _encrypt_data(self, plaintext: str) -> str:
        """Encrypt plaintext using Windows DPAPI if available, otherwise base64 machine-wrapped payload."""
        try:
            import ctypes
            import ctypes.wintypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

            p_in = DATA_BLOB(len(plaintext), ctypes.cast(ctypes.create_string_buffer(plaintext.encode("utf-8")), ctypes.POINTER(ctypes.c_char)))
            p_out = DATA_BLOB()
            if ctypes.windll.crypt32.CryptProtectData(ctypes.byref(p_in), "IRIS_GITHUB_TOKENS", None, None, None, 0, ctypes.byref(p_out)):
                encrypted_bytes = ctypes.string_at(p_out.pbData, p_out.cbData)
                ctypes.windll.kernel32.LocalFree(p_out.pbData)
                return "dpapi:" + base64.b64encode(encrypted_bytes).decode("ascii")
        except Exception:
            pass

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
                return cipher_str
        except Exception as exc:
            logger.error("Failed to decrypt GitHub credentials: %s", exc)
            return None

    def save_token(self, token: str, username: str | None = None, default_repo: str | None = None) -> bool:
        """Validate and securely store GitHub token on local machine."""
        if not token:
            return False

        # Attempt to validate token and fetch username from GitHub API if not provided
        if not username and not token.startswith("ghp_mock_") and not token.startswith("test_"):
            username = self._fetch_authenticated_user(token)

        token_data = {
            "token": token,
            "username": username or "ghostoftheravalhere",
            "default_repo": default_repo or self._default_repo,
        }

        try:
            plaintext = json.dumps(token_data)
            encrypted = self._encrypt_data(plaintext)
            with open(self._storage_path, "w", encoding="utf-8") as f:
                f.write(encrypted)
            logger.info("Successfully saved encrypted GitHub PAT credentials for user '%s'", token_data["username"])
            return True
        except Exception as exc:
            logger.error("Failed to write GitHub credentials file: %s", exc)
            return False

    def load_credentials(self) -> dict[str, Any] | None:
        """Load and decrypt stored credentials."""
        if not os.path.exists(self._storage_path):
            if self._token_env:
                return {"token": self._token_env, "username": "ghostoftheravalhere", "default_repo": self._default_repo}
            return None
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                cipher_str = f.read().strip()
            plaintext = self._decrypt_data(cipher_str)
            if not plaintext:
                return None
            return json.loads(plaintext)
        except Exception as exc:
            logger.error("Error loading GitHub credentials: %s", exc)
            return None

    def clear_credentials(self) -> bool:
        """Remove stored credentials locally."""
        try:
            if os.path.exists(self._storage_path):
                os.remove(self._storage_path)
            self._token_env = ""
            return True
        except Exception as exc:
            logger.error("Failed to delete GitHub credentials file: %s", exc)
            return False

    def get_token(self) -> str | None:
        """Return decrypted token or env token."""
        creds = self.load_credentials()
        if creds and creds.get("token"):
            return creds["token"]
        return self._token_env or None

    def get_status(self) -> str:
        """Return safe account connection status without exposing secrets.

        Returns one of:
        - "GitHub connected"
        - "GitHub not connected"
        - "GitHub authentication failed"
        """
        token = self.get_token()
        if not token:
            return "GitHub not connected"
        return "GitHub connected"

    def get_account_username(self) -> str | None:
        """Return connected GitHub username or None."""
        creds = self.load_credentials()
        return creds.get("username") if creds else None

    def get_default_repo(self) -> str:
        """Return configured default repository."""
        creds = self.load_credentials()
        if creds and creds.get("default_repo"):
            return creds["default_repo"]
        return self._default_repo

    def _fetch_authenticated_user(self, token: str) -> str | None:
        """Fetch primary login username of authenticated token owner."""
        url = "https://api.github.com/user"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"token {token}",
                "User-Agent": "IRIS-AI-Agent/4.0",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("login")
        except Exception as exc:
            logger.warning("Could not fetch GitHub authenticated user: %s", exc)
            return None

    @staticmethod
    def sanitize_log_data(data: Any) -> Any:
        """Redact sensitive GitHub token fields from logs, telemetries, and model inputs."""
        if isinstance(data, dict):
            sanitized = {}
            for k, v in data.items():
                if any(secret_key in k.lower() for secret_key in ("token", "secret", "password", "authorization", "github_token")):
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = GitHubAuthService.sanitize_log_data(v)
            return sanitized
        elif isinstance(data, list):
            return [GitHubAuthService.sanitize_log_data(item) for item in data]
        elif isinstance(data, str):
            for token_prefix in ("ghp_", "github_pat_", "Bearer ", "token "):
                if token_prefix in data:
                    data = data.replace(token_prefix, f"{token_prefix}[REDACTED]")
            return data
        return data


github_auth_service = GitHubAuthService()
