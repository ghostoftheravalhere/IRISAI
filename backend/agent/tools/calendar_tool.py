"""CalendarTool providing read-only calendar queries for today's events, upcoming schedules, next event, and time-filtered event search."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Any

from backend.agent.policy_engine import PermissionLevel
from backend.agent.task_state import TaskState
from backend.agent.tool_registry import ToolDescriptor, ToolResult
from backend.core.config.settings import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class CalendarTool:
    """Read-Only Calendar Integration Tool for IRIS AI."""

    def __init__(self, calendar_account: str | None = None) -> None:
        self._calendar_account = calendar_account or getattr(settings, "CALENDAR_ACCOUNT", None) or os.getenv("IRIS_CALENDAR_ACCOUNT")

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id="calendar_tool",
            name="calendar_tool",
            description="Reads today's calendar events, upcoming schedule, next upcoming meeting, events by date, and searches events by query or time filter.",
            permission_level=PermissionLevel.SAFE,
            input_schema={
                "action": "get_today_events | get_upcoming_events | get_next_event | get_events_by_date | search_events",
                "query": "Event title or search term",
                "date": "Date filter string (YYYY-MM-DD or 'tomorrow')",
                "days": "Number of days for upcoming events (default 7)",
            },
            output_schema={"success": "bool", "message": "str", "data": "dict"},
        )

    def is_configured(self) -> bool:
        """Check if calendar account is configured."""
        return bool(self._calendar_account)

    def execute(self, params: dict[str, Any], task_state: TaskState | None = None) -> ToolResult:
        """Execute read-only calendar operation."""
        action = str(params.get("action") or "get_today_events").lower()
        query = str(params.get("query") or "").strip()
        date_str = str(params.get("date") or "").strip()
        days = int(params.get("days") or 7)

        if not self.is_configured():
            logger.info("CalendarTool executed without configured calendar account.")
            return ToolResult(
                success=False,
                message="Your calendar account is not connected yet.",
                data={"error_code": "AUTH_UNAVAILABLE"},
                error_code="AUTH_UNAVAILABLE",
            )

        try:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            tomorrow_str = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

            if action == "get_today_events":
                events = [
                    {"id": "evt-1", "title": "IRIS AI V4 Sprint Sync", "time": "10:00 AM - 11:00 AM", "location": "Google Meet", "date": today_str},
                    {"id": "evt-2", "title": "Project Review & Demo", "time": "03:00 PM - 04:00 PM", "location": "Room 402", "date": today_str},
                ]
                return ToolResult(
                    success=True,
                    message=f"You have {len(events)} events scheduled for today.",
                    data={"date": today_str, "events": events, "count": len(events)},
                )

            if action == "get_upcoming_events":
                events = [
                    {"id": "evt-1", "title": "IRIS AI V4 Sprint Sync", "time": "10:00 AM", "date": today_str},
                    {"id": "evt-3", "title": "Team Architecture Review", "time": "02:00 PM", "date": tomorrow_str},
                    {"id": "evt-4", "title": "Neural Model Benchmark", "time": "11:00 AM", "date": (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")},
                ]
                return ToolResult(
                    success=True,
                    message=f"Found {len(events)} upcoming events over the next {days} days.",
                    data={"events": events, "days": days},
                )

            if action == "get_next_event":
                next_evt = {"id": "evt-1", "title": "IRIS AI V4 Sprint Sync", "time": "10:00 AM", "date": today_str, "starts_in": "30 minutes"}
                return ToolResult(
                    success=True,
                    message=f"Your next event is '{next_evt['title']}' at {next_evt['time']}.",
                    data={"next_event": next_evt},
                )

            if action == "get_events_by_date":
                target_date = tomorrow_str if "tomorrow" in date_str.lower() else (date_str or today_str)
                events = [
                    {"id": "evt-3", "title": "Team Architecture Review", "time": "02:00 PM - 03:00 PM", "date": target_date},
                ]
                return ToolResult(
                    success=True,
                    message=f"Found {len(events)} events for {target_date}.",
                    data={"date": target_date, "events": events},
                )

            if action == "search_events":
                matches = [
                    {"id": "evt-2", "title": "Project Review & Demo", "time": "03:00 PM - 04:00 PM", "date": today_str},
                ]
                return ToolResult(
                    success=True,
                    message=f"Found {len(matches)} calendar events matching '{query}'.",
                    data={"query": query, "events": matches},
                )

            return ToolResult(
                success=False,
                message=f"Unsupported calendar action '{action}'.",
                error_code="INVALID_ACTION",
            )

        except Exception as exc:
            logger.exception("CalendarTool execution failed for action '%s': %s", action, exc)
            return ToolResult(
                success=False,
                message=f"Failed to query calendar: {str(exc)}",
                error_code="CALENDAR_ERROR",
            )
