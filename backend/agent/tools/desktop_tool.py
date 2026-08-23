"""DesktopTool wrapping low-level ActionEngine and DesktopController capabilities."""

from __future__ import annotations

from typing import Any

from backend.agent.policy_engine import PermissionLevel
from backend.agent.task_state import TaskState
from backend.agent.tool_registry import ToolDescriptor, ToolResult
from backend.automation.action_engine import ActionEngine, ActionRequest, CanonicalAction
from backend.automation.controller import DesktopController
from backend.perception.screen_grounding_engine import screen_grounding_engine
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

        if action_str == "unknown_goal":
            unrec_goal = str(params.get("goal") or target or "")
            return ToolResult(False, f"I'm not sure which application or action you mean by '{unrec_goal}'. Could you please specify?", error_code="UNRECOGNIZED_GOAL")

        if action_str == "open_application" or action_str == "open_app":
            app_name = str(target or "").strip()
            if not app_name:
                return ToolResult(False, "No application target specified", error_code="TARGET_NOT_FOUND")

            if not self._desktop_controller.is_application_supported(app_name):
                logger.warning("DesktopTool rejected unverified target: '%s'", app_name)
                return ToolResult(False, f"Application target '{app_name}' not found or unsupported", error_code="TARGET_NOT_FOUND")

            req = ActionRequest(action=CanonicalAction.OPEN_APPLICATION, target_phrase=app_name)
            res = self._action_engine.execute(req)
            if res.success:
                if task_state:
                    task_state.active_application = app_name
                    task_state.last_resolved_target = app_name
                return ToolResult(True, res.message, data={"canonical_action": "OPEN_APPLICATION", "target": app_name})
            else:
                return ToolResult(False, res.message, error_code="TARGET_NOT_FOUND", data={"target": app_name})

        if action_str == "click":
            x = params.get("x")
            y = params.get("y")
            req = ActionRequest(action=CanonicalAction.CLICK, target_phrase=str(target or ""), target_x=x, target_y=y)
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message, data={"canonical_action": "PRIMARY_CLICK"})

        if action_str == "right_click":
            x = params.get("x")
            y = params.get("y")
            req = ActionRequest(action=CanonicalAction.RIGHT_CLICK, target_phrase=str(target or ""), target_x=x, target_y=y)
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message, data={"canonical_action": "RIGHT_CLICK"})

        if action_str == "double_click":
            x = params.get("x")
            y = params.get("y")
            req = ActionRequest(action=CanonicalAction.DOUBLE_CLICK, target_phrase=str(target or ""), target_x=x, target_y=y)
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message, data={"canonical_action": "DOUBLE_CLICK"})

        if action_str == "type_text" or action_str == "type":
            type_str = str(text or target or "")
            req = ActionRequest(action=CanonicalAction.TYPE_TEXT, text_payload=type_str)
            res = self._action_engine.execute(req)
            err = None if res.success else ("PY_AUTOGUI_FAILSAFE" if "failsafe" in res.message.lower() else "INPUT_FAILURE")
            return ToolResult(res.success, res.message, error_code=err, data={"canonical_action": "TYPE_TEXT", "text": type_str})

        if action_str == "hotkey":
            if isinstance(keys, list):
                res_ok = self._desktop_controller.hotkey(*keys)
                return ToolResult(res_ok, f"Hotkey {keys} executed")
            req = ActionRequest(action=CanonicalAction.HOTKEY, params={"keys": keys or []})
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message)

        if action_str == "copy":
            req = ActionRequest(action=CanonicalAction.COPY)
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message, data={"canonical_action": "COPY"})

        if action_str == "paste":
            req = ActionRequest(action=CanonicalAction.PASTE)
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message, data={"canonical_action": "PASTE"})

        if action_str == "scroll_down":
            clicks = params.get("clicks", -5)
            req = ActionRequest(action=CanonicalAction.SCROLL_DOWN, params={"clicks": clicks})
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message, data={"canonical_action": "SCROLL_DOWN"})

        if action_str == "scroll_up":
            clicks = params.get("clicks", 5)
            req = ActionRequest(action=CanonicalAction.SCROLL_UP, params={"clicks": clicks})
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message, data={"canonical_action": "SCROLL_UP"})

        if action_str == "find_element":
            target_query = str(target or params.get("query") or "").strip()
            res = screen_grounding_engine.ground_query(target_query)
            if not res.success:
                err = res.error_code or "NOT_FOUND"
                return ToolResult(False, res.clarification_message or f"Could not find element '{target_query}'", error_code=err)
            return ToolResult(True, f"Found '{res.target.name}' ({res.target.role}) at center {res.target.center}", data=res.target.to_safe_dict())

        if action_str == "click_element" or action_str == "click_grounded":
            target_query = str(target or params.get("query") or "").strip()
            res = screen_grounding_engine.ground_query(target_query)
            if not res.success:
                err = res.error_code or "NOT_FOUND"
                return ToolResult(False, res.clarification_message or f"Could not find element '{target_query}'", error_code=err)
            req = ActionRequest(action=CanonicalAction.CLICK, target_phrase=res.target.name, target_x=res.target.center[0], target_y=res.target.center[1])
            act_res = self._action_engine.execute(req)
            return ToolResult(act_res.success, act_res.message, data={"canonical_action": "PRIMARY_CLICK", "target": res.target.to_safe_dict()})

        if action_str == "spatial_click":
            deictic_term = str(target or "this").strip()
            res = screen_grounding_engine.ground_query(deictic_term)
            if not res.success:
                err = res.error_code or "SPATIAL_FAILED"
                return ToolResult(False, res.clarification_message or "Spatial resolution failed", error_code=err)
            req = ActionRequest(action=CanonicalAction.CLICK, target_phrase=res.target.name, target_x=res.target.center[0], target_y=res.target.center[1])
            act_res = self._action_engine.execute(req)
            return ToolResult(act_res.success, act_res.message, data={"canonical_action": "PRIMARY_CLICK", "target": res.target.to_safe_dict()})

        if action_str == "query_visible_elements" or action_str == "visible_elements":
            elements = screen_grounding_engine.extract_screen_elements()
            names = [f"'{e.name}' ({e.role})" for e in elements[:10]]
            return ToolResult(True, f"Visible elements on screen: {', '.join(names)}", data={"elements": [e.to_safe_dict() for e in elements]})

        if action_str == "close_window" or action_str == "close":
            req = ActionRequest(action=CanonicalAction.CLOSE_WINDOW, target_phrase=str(target or ""))
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message, data={"canonical_action": "CLOSE_WINDOW"})

        if action_str == "minimize_window" or action_str == "minimize":
            req = ActionRequest(action=CanonicalAction.MINIMIZE_WINDOW)
            res = self._action_engine.execute(req)
            return ToolResult(res.success, res.message, data={"canonical_action": "MINIMIZE_WINDOW"})

        if action_str == "unknown_goal":
            return ToolResult(False, "Sorry, I didn't understand that command.", error_code="UNKNOWN_COMMAND")

        return ToolResult(False, f"Unsupported desktop action '{action_str}'")
