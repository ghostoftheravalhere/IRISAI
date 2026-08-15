"""BrowserTool providing browser navigation and tab control capability wrappers."""

from __future__ import annotations

from typing import Any

from backend.agent.policy_engine import PermissionLevel
from backend.agent.task_state import TaskState
from backend.agent.tool_registry import ToolDescriptor, ToolResult
from backend.automation.action_engine import ActionEngine, ActionRequest, CanonicalAction
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class BrowserTool:
    """Agent Tool wrapping browser automation and tab navigation."""

    def __init__(self, action_engine: ActionEngine | None = None) -> None:
        self._action_engine = action_engine or ActionEngine()

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id="browser_tool",
            name="browser_tool",
            description="Navigates browser URLs, manages browser tabs, and performs browser interactions.",
            permission_level=PermissionLevel.SAFE,
            input_schema={
                "action": "open_url | new_tab | close_tab | switch_tab",
                "url": "Target URL to open",
                "tab_index": "Tab index to target (e.g., 1, 2)",
            },
            output_schema={"success": "bool", "message": "str"},
        )

    def execute(self, params: dict[str, Any], task_state: TaskState | None = None) -> ToolResult:
        """Execute browser action."""
        action = str(params.get("action") or "open_url").lower().strip()
        url = str(params.get("url") or params.get("target") or "").strip()

        if action == "open_url" or action == "navigate":
            if not url:
                return ToolResult(False, "URL parameter missing")
            if not (url.startswith("http://") or url.startswith("https://")):
                url = "https://" + url
            req = ActionRequest(action=CanonicalAction.BROWSER_SEARCH, text_payload=url)
            res = self._action_engine.execute(req)
            if task_state:
                task_state.active_application = "browser"
            return ToolResult(res.success, f"Navigated to '{url}'")

        if action == "new_tab":
            req = ActionRequest(action=CanonicalAction.HOTKEY, params={"keys": ["ctrl", "t"]})
            res = self._action_engine.execute(req)
            return ToolResult(res.success, "Opened new browser tab")

        if action == "close_tab":
            req = ActionRequest(action=CanonicalAction.HOTKEY, params={"keys": ["ctrl", "w"]})
            res = self._action_engine.execute(req)
            return ToolResult(res.success, "Closed browser tab")

        if action == "switch_tab":
            index = int(params.get("tab_index") or 1)
            req = ActionRequest(action=CanonicalAction.HOTKEY, params={"keys": ["ctrl", str(index)]})
            res = self._action_engine.execute(req)
            return ToolResult(res.success, f"Switched to browser tab {index}")

        return ToolResult(False, f"Unsupported browser action '{action}'")
