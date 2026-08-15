"""Security Policy Engine evaluating tool permission levels and authorization gates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class PermissionLevel(str, Enum):
    """Authorization classification levels for tool execution."""

    SAFE = "SAFE"                          # Auto-execute (read local file, open app, search web)
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED" # User confirmation required (delete file, write code, send email)
    PRIVILEGED = "PRIVILEGED"              # Admin authorization required
    BLOCKED = "BLOCKED"                    # Destructive system operations permanently blocked


@dataclass(frozen=True)
class PolicyEvaluationResult:
    """Outcome of policy evaluation for a proposed tool execution."""

    allowed: bool
    permission_level: PermissionLevel
    requires_user_confirmation: bool
    reason: str


class PolicyEngine:
    """Evaluates security rules, tool permission levels, and confirmation boundaries."""

    def __init__(self, strict_mode: bool = False) -> None:
        self._strict_mode = strict_mode
        self._blocked_commands = {"rm -rf", "format C:", "del /s", "drop database", "shutdown"}

    def evaluate(
        self,
        tool_name: str,
        permission_level: PermissionLevel,
        params: dict[str, Any],
    ) -> PolicyEvaluationResult:
        """Evaluate authorization policy for a proposed tool call."""
        # 1. Check blocked system patterns
        param_str = str(params).lower()
        for cmd in self._blocked_commands:
            if cmd in param_str:
                logger.warning("Blocked security violation in tool '%s': %s", tool_name, cmd)
                return PolicyEvaluationResult(
                    allowed=False,
                    permission_level=PermissionLevel.BLOCKED,
                    requires_user_confirmation=False,
                    reason=f"Action contains blocked system operation '{cmd}'",
                )

        if permission_level == PermissionLevel.BLOCKED:
            return PolicyEvaluationResult(
                allowed=False,
                permission_level=PermissionLevel.BLOCKED,
                requires_user_confirmation=False,
                reason=f"Tool '{tool_name}' is permanently blocked",
            )

        # Action-level confirmation rules (e.g., delete_file)
        action_name = str(params.get("action") or "").lower()
        if action_name in ("delete_file", "delete", "remove_file", "write_file") or permission_level == PermissionLevel.CONFIRMATION_REQUIRED or self._strict_mode:
            return PolicyEvaluationResult(
                allowed=True,
                permission_level=PermissionLevel.CONFIRMATION_REQUIRED,
                requires_user_confirmation=True,
                reason=f"Action '{action_name or tool_name}' requires explicit user confirmation",
            )

        if permission_level == PermissionLevel.PRIVILEGED:
            return PolicyEvaluationResult(
                allowed=False,
                permission_level=PermissionLevel.PRIVILEGED,
                requires_user_confirmation=True,
                reason=f"Tool '{tool_name}' requires privileged administrative authorization",
            )

        return PolicyEvaluationResult(
            allowed=True,
            permission_level=PermissionLevel.SAFE,
            requires_user_confirmation=False,
            reason=f"Tool '{tool_name}' is approved for automatic execution",
        )
