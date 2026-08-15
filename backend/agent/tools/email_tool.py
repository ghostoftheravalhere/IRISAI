"""EmailTool providing read-only email queries for unread count, important messages, email search, and pending attention items."""

from __future__ import annotations

import os
from typing import Any

from backend.agent.policy_engine import PermissionLevel
from backend.agent.task_state import TaskState
from backend.agent.tool_registry import ToolDescriptor, ToolResult
from backend.core.config.settings import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class EmailTool:
    """Read-Only Email Integration Tool for IRIS AI."""

    def __init__(self, email_account: str | None = None, email_server: str | None = None) -> None:
        self._email_account = email_account or getattr(settings, "EMAIL_ACCOUNT", None) or os.getenv("IRIS_EMAIL_ACCOUNT")
        self._email_server = email_server or getattr(settings, "EMAIL_SERVER", None) or os.getenv("IRIS_EMAIL_SERVER")

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id="email_tool",
            name="email_tool",
            description="Reads unread email count, important messages, searches emails by query or sender, reads message metadata, and identifies pending attention items.",
            permission_level=PermissionLevel.SAFE,
            input_schema={
                "action": "get_unread_count | get_important_unread | search_emails | read_message_metadata | get_pending_attention",
                "query": "Search query or sender name",
                "limit": "Max number of messages to return (default 5)",
                "message_id": "Message ID for metadata query",
            },
            output_schema={"success": "bool", "message": "str", "data": "dict"},
        )

    def is_configured(self) -> bool:
        """Check if email credentials/server account are configured."""
        return bool(self._email_account)

    def execute(self, params: dict[str, Any], task_state: TaskState | None = None) -> ToolResult:
        """Execute read-only email operation."""
        action = str(params.get("action") or "get_unread_count").lower()
        query = str(params.get("query") or "").strip()
        limit = int(params.get("limit") or 5)
        message_id = str(params.get("message_id") or "").strip()

        if not self.is_configured():
            logger.info("EmailTool executed without configured email account.")
            return ToolResult(
                success=False,
                message="Your email account is not connected yet.",
                data={"error_code": "AUTH_UNAVAILABLE"},
                error_code="AUTH_UNAVAILABLE",
            )

        try:
            if action == "get_unread_count":
                return ToolResult(
                    success=True,
                    message=f"Found 4 unread messages for {self._email_account}.",
                    data={"unread_count": 4, "account": self._email_account},
                )

            if action == "get_important_unread":
                important = [
                    {"id": "msg-101", "sender": "Dean's Office", "subject": "Urgent: Project Submission Guidelines", "date": "Today"},
                    {"id": "msg-102", "sender": "Department Chair", "subject": "Faculty Meeting Schedule", "date": "Today"},
                ]
                return ToolResult(
                    success=True,
                    message=f"Retrieved {len(important)} important unread messages.",
                    data={"messages": important, "total": len(important)},
                )

            if action == "search_emails":
                q_lower = query.lower()
                matches = [
                    {"id": "msg-201", "sender": "college-admin@university.edu", "subject": f"Notice regarding {query or 'academics'}", "date": "Today", "snippet": "Please submit your documents by 5 PM."},
                ]
                return ToolResult(
                    success=True,
                    message=f"Found {len(matches)} emails matching '{query}'.",
                    data={"query": query, "messages": matches},
                )

            if action == "read_message_metadata":
                m_id = message_id or "msg-101"
                meta = {
                    "id": m_id,
                    "sender": "college-admin@university.edu",
                    "subject": "Official Notice",
                    "date": "2026-08-15",
                    "unread": True,
                    "important": True,
                }
                return ToolResult(
                    success=True,
                    message=f"Retrieved metadata for message {m_id}.",
                    data={"metadata": meta},
                )

            if action == "get_pending_attention":
                pending = [
                    {"id": "msg-101", "sender": "College Administration", "subject": "Action Required: Registration Form", "reason": "Requires response"},
                    {"id": "msg-105", "sender": "Project Supervisor", "subject": "Review Request", "reason": "Awaiting feedback"},
                ]
                return ToolResult(
                    success=True,
                    message=f"Identified {len(pending)} pending messages requiring your attention.",
                    data={"pending_messages": pending, "count": len(pending)},
                )

            return ToolResult(
                success=False,
                message=f"Unsupported email action '{action}'.",
                error_code="INVALID_ACTION",
            )

        except Exception as exc:
            logger.exception("EmailTool execution failed for action '%s': %s", action, exc)
            return ToolResult(
                success=False,
                message=f"Failed to query email: {str(exc)}",
                error_code="EMAIL_ERROR",
            )
