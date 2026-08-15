"""DesktopTool wrapping low-level ActionEngine and DesktopController capabilities."""

from __future__ import annotations

from typing import Any

from backend.agent.policy_engine import PermissionLevel
from backend.agent.task_state import TaskState
from backend.agent.tool_registry import ToolDescriptor, ToolResult
from backend.automation.action_engine import ActionEngine, ActionRequest, CanonicalAction
from backend.automation.controller import DesktopController
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class DesktopTool:
    """Agent Tool wrapping UI automation, mouse clicks, typing, hotkeys, and window control."""

    def __init__(
        self,
        action_engine: ActionEngine | None = None,
        desktop_controller: DesktopController | None = None,
    ) -> None:
        ctrl = desktop_controller or DesktopController()
        self._action_engine = action_engine or ActionEngine(desktop_controller=ctrl)
        self._desktop_controller = ctrl

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id="desktop_tool",
            name="desktop_tool",
            description="Executes UI automation, window control, mouse clicks, text typing, and application launching.",
            permission_level=PermissionLevel.SAFE,
            input_schema={
                "action": "open_application | click | right_click | double_click | type_text | hotkey | close_window | minimize_window",
                "target": "Target name, app name, or button label",
                "text": "Text to type",
                "keys": "List of key names for hotkey",
            },
            output_schema={"success": "bool", "message": "str"},
        )

    def execute(self, params: dict[str, Any], task_state: TaskState | None = None) -> ToolResult:
        """Execute desktop UI action."""
        action_str = str(params.get("action") or "").lower().strip()
        target = params.get("target") or params.get("target_phrase")
        text = params.get("text") or params.get("text_payload")
        keys = params.get("keys")

        if action_str == "open_application" or action_str == "open_app":
            app_name = str(target or "").strip()
            if not app_name:
                return ToolResult(False, "No application target specified")
            req = ActionRequest(action=CanonicalAction.OPEN_APPLICATION, target_phrase=app_name)
            res = self._action_engine.execute(req)
            if task_state:
                task_state.active_application = app_name
                task_state.last_resolved_target = app_name
            return ToolResult(res.success, res.message)

        if action_str == "click":
            x = params.get("x")
            y = params.get("y")
            req = ActionRequest(action=CanonicalAction.CLICK, target_phrase=str(target or ""), target_x=x, target_y=y)
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message)

        if action_str == "right_click":
            x = params.get("x")
            y = params.get("y")
            req = ActionRequest(action=CanonicalAction.RIGHT_CLICK, target_phrase=str(target or ""), target_x=x, target_y=y)
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message)

        if action_str == "double_click":
            x = params.get("x")
            y = params.get("y")
            req = ActionRequest(action=CanonicalAction.DOUBLE_CLICK, target_phrase=str(target or ""), target_x=x, target_y=y)
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message)

        if action_str == "type_text" or action_str == "type":
            type_str = str(text or target or "")
            req = ActionRequest(action=CanonicalAction.TYPE_TEXT, text_payload=type_str)
            res = self._action_engine.execute(req)
            err = None if res.success else ("PY_AUTOGUI_FAILSAFE" if "failsafe" in res.message.lower() else "INPUT_FAILURE")
            return ToolResult(res.success, res.message, error_code=err)

        if action_str == "hotkey":
            if isinstance(keys, list):
                res_ok = self._desktop_controller.hotkey(*keys)
                return ToolResult(res_ok, f"Hotkey {keys} executed")
            req = ActionRequest(action=CanonicalAction.HOTKEY, params={"keys": keys or []})
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message)

        if action_str == "close_window" or action_str == "close":
            req = ActionRequest(action=CanonicalAction.CLOSE_WINDOW, target_phrase=str(target or ""))
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message)

        if action_str == "minimize_window" or action_str == "minimize":
            req = ActionRequest(action=CanonicalAction.MINIMIZE_WINDOW)
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message)

        return ToolResult(False, f"Unsupported desktop action '{action_str}'")
