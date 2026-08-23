"""SecretRedactor providing automated detection and redaction of passwords, API keys, and sensitive tokens."""

from __future__ import annotations

import re
from typing import Any


class SecretRedactor:
    """Detects and redacts sensitive credentials, secrets, and auth tokens from interaction dataset records."""

    SECRET_PATTERNS: list[re.Pattern] = [
        # Passwords / Secrets in params or text
        re.compile(r"(?i)(password|passwd|secret|api_key|token|auth_token|access_token|private_key)\s*[:=]\s*['\"]?([^\s'\"]+)['\"]?"),
        # OpenAI / Anthropic / Gemini API Keys
        re.compile(r"(sk-[a-zA-Z0-9]{20,})|(AIzaSy[a-zA-Z0-9_-]{33})"),
        # Bearer tokens
        re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.=]+"),
        # JWT tokens
        re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),
        # Cookies / Session IDs with secret values
        re.compile(r"(?i)(sessionid|cookie)\s*=\s*[a-zA-Z0-9_-]{16,}"),
    ]

    SENSITIVE_PARAM_KEYS: set[str] = {
        "password", "passwd", "secret", "api_key", "token",
        "auth_token", "access_token", "private_key", "credentials", "cookie"
    }

    @classmethod
    def redact_text(cls, text: str) -> str:
        """Redact sensitive patterns from raw string text."""
        if not text:
            return ""

        redacted = text
        for pattern in cls.SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED_SECRET]", redacted)
        return redacted

    @classmethod
    def contains_unredacted_secret(cls, obj: Any) -> bool:
        """Return True if unredacted secret patterns remain in data object."""
        if isinstance(obj, str):
            for pattern in cls.SECRET_PATTERNS:
                if pattern.search(obj):
                    return True
            return False

        if isinstance(obj, dict):
            for k, v in obj.items():
                if str(k).lower() in cls.SENSITIVE_PARAM_KEYS and str(v) != "[REDACTED_SECRET]":
                    return True
                if cls.contains_unredacted_secret(v):
                    return True
            return False

        if isinstance(obj, list):
            return any(cls.contains_unredacted_secret(item) for item in obj)

        return False

    @classmethod
    def sanitize(cls, data: Any) -> Any:
        """Recursively sanitize dictionaries, lists, and strings replacing secret values with [REDACTED_SECRET]."""
        if isinstance(data, str):
            return cls.redact_text(data)

        if isinstance(data, dict):
            sanitized_dict = {}
            for k, v in data.items():
                if str(k).lower() in cls.SENSITIVE_PARAM_KEYS:
                    sanitized_dict[k] = "[REDACTED_SECRET]"
                else:
                    sanitized_dict[k] = cls.sanitize(v)
            return sanitized_dict

        if isinstance(data, list):
            return [cls.sanitize(item) for item in data]

        return data
