"""Unified ActionEngine executing canonical ActionRequests for all input modalities."""

from __future__ import annotations

from threading import RLock
from typing import Any

from backend.automation.action_models import ActionRequest, ActionResult, CanonicalAction
from backend.automation.controller import DesktopController
from backend.utils.logger import get_logger
from backend.voice.command_parser import VoiceIntent, VoiceIntentType

logger = get_logger(__name__)

_VOICE_INTENT_MAP: dict[VoiceIntentType, CanonicalAction] = {
    VoiceIntentType.OPEN_APPLICATION: CanonicalAction.OPEN_APPLICATION,
    VoiceIntentType.OPEN_CHAT: CanonicalAction.OPEN_CHAT,
    VoiceIntentType.OPEN_CHROME: CanonicalAction.OPEN_APPLICATION,
    VoiceIntentType.OPEN_NOTEPAD: CanonicalAction.OPEN_APPLICATION,
    VoiceIntentType.CLOSE_APPLICATION: CanonicalAction.CLOSE_APPLICATION,
    VoiceIntentType.CLOSE_WINDOW: CanonicalAction.CLOSE_WINDOW,
    VoiceIntentType.MINIMIZE_WINDOW: CanonicalAction.MINIMIZE_WINDOW,
    VoiceIntentType.BROWSER_SEARCH: CanonicalAction.BROWSER_SEARCH,
    VoiceIntentType.HOTKEY: CanonicalAction.HOTKEY,
    VoiceIntentType.TYPE_TEXT: CanonicalAction.TYPE_TEXT,
    VoiceIntentType.PRESS_KEY: CanonicalAction.PRESS_KEY,
    VoiceIntentType.WAIT_FOR_WINDOW: CanonicalAction.WAIT_FOR_WINDOW,
    VoiceIntentType.ACTIVATE_WINDOW: CanonicalAction.ACTIVATE_WINDOW,
    VoiceIntentType.VERIFY_WINDOW_ACTIVE: CanonicalAction.VERIFY_WINDOW_ACTIVE,
    VoiceIntentType.PRIMARY_CLICK: CanonicalAction.CLICK,
    VoiceIntentType.RIGHT_CLICK: CanonicalAction.RIGHT_CLICK,
    VoiceIntentType.DOUBLE_CLICK: CanonicalAction.DOUBLE_CLICK,
    VoiceIntentType.START_SELECTING: CanonicalAction.START_SELECTING,
    VoiceIntentType.STOP_SELECTING: CanonicalAction.STOP_SELECTING,
    VoiceIntentType.SCROLL_DOWN: CanonicalAction.SCROLL_DOWN,
    VoiceIntentType.SCROLL_UP: CanonicalAction.SCROLL_UP,
    VoiceIntentType.VOLUME_UP: CanonicalAction.VOLUME_UP,
    VoiceIntentType.VOLUME_DOWN: CanonicalAction.VOLUME_DOWN,
    VoiceIntentType.MUTE: CanonicalAction.MUTE,
    VoiceIntentType.COPY: CanonicalAction.COPY,
    VoiceIntentType.PASTE: CanonicalAction.PASTE,
    VoiceIntentType.SELECT_ALL: CanonicalAction.SELECT,
    VoiceIntentType.TAKE_SCREENSHOT: CanonicalAction.SCREENSHOT,
    VoiceIntentType.NO_INTENT: CanonicalAction.NO_ACTION,
}


class ActionEngine:
    """Canonical desktop automation execution engine for voice, gaze, and UI interactions."""

    def __init__(
        self,
        desktop_controller: DesktopController,
        selection_manager: Any | None = None,
    ) -> None:
        self._desktop_controller = desktop_controller
        self._selection_manager = selection_manager
        self._lock = RLock()

    @staticmethod
    def from_voice_intent(voice_intent: VoiceIntent, source_modality: str = "voice") -> ActionRequest:
        """Map legacy VoiceIntent to canonical ActionRequest."""
        canonical = _VOICE_INTENT_MAP.get(voice_intent.intent, CanonicalAction.NO_ACTION)
        text_payload = voice_intent.query or voice_intent.params.get("text") if voice_intent.params else None
        if not text_payload and canonical == CanonicalAction.TYPE_TEXT:
            text_payload = voice_intent.text

        gaze_x = voice_intent.params.get("gaze_x") if voice_intent.params else None
        gaze_y = voice_intent.params.get("gaze_y") if voice_intent.params else None

        return ActionRequest(
            action=canonical,
            source_modality=source_modality,
            target_phrase=voice_intent.target,
            target_x=gaze_x,
            target_y=gaze_y,
            text_payload=text_payload,
            params=voice_intent.params,
            confidence=voice_intent.confidence,
        )

    def execute(self, request: ActionRequest) -> ActionResult:
        """Execute a canonical ActionRequest via DesktopController primitives."""
        with self._lock:
            action = request.action
            logger.info("Executing canonical ActionRequest action=%s source=%s target=%s", action.value, request.source_modality, request.target_phrase)

            if action == CanonicalAction.NO_ACTION:
                return ActionResult(False, action, "No action specified.")

            # Spatial Mouse Clicks
            if action in {CanonicalAction.CLICK, CanonicalAction.DOUBLE_CLICK, CanonicalAction.RIGHT_CLICK}:
                return self._execute_click(request)

            if action in {CanonicalAction.OPEN_APPLICATION, CanonicalAction.OPEN_CHAT}:
                target = (request.target_phrase or "").strip()
                if not target:
                    return ActionResult(False, action, "No application/chat specified.")
                success = self._desktop_controller.open_application(target.lower())
                label = f"Chat '{target}'" if action == CanonicalAction.OPEN_CHAT else target.title()
                msg = f"{label} opened" if success else f"Failed to open {label}"
                return ActionResult(success, action, msg)

            if action == CanonicalAction.CLOSE_WINDOW:
                success = self._desktop_controller.close_window()
                msg = "Window closed" if success else "Failed to close window"
                return ActionResult(success, action, msg)

            if action == CanonicalAction.CLOSE_APPLICATION:
                target = (request.target_phrase or "").strip().lower()
                if not target or target == "window":
                    success = self._desktop_controller.close_window()
                    msg = "Window closed" if success else "Failed to close window"
                    return ActionResult(success, action, msg)
                res = self._desktop_controller.close_application(target)
                msg = f"{target.title()} closed" if res.success else f"Failed to close {target.title()}"
                return ActionResult(res.success, action, msg)

            if action == CanonicalAction.MINIMIZE_WINDOW:
                success = self._desktop_controller.hotkey("win", "down")
                return ActionResult(success, action, "Window minimized" if success else "Minimize failed")

            if action == CanonicalAction.MAXIMIZE_WINDOW:
                success = self._desktop_controller.hotkey("win", "up")
                return ActionResult(success, action, "Window maximized" if success else "Maximize failed")

            # Text & Keyboard Actions
            if action == CanonicalAction.TYPE_TEXT:
                text = request.text_payload or request.params.get("text", "")
                success = self._desktop_controller.type_text(text)
                return ActionResult(success, action, f"Typed '{text}'" if success else "Typing failed")

            if action == CanonicalAction.PRESS_KEY:
                key = request.params.get("key", "enter")
                success = self._desktop_controller.press(key)
                return ActionResult(success, action, f"Pressed key '{key}'")

            if action == CanonicalAction.HOTKEY:
                keys = request.params.get("keys", ["ctrl", "c"])
                success = self._desktop_controller.hotkey(*keys)
                return ActionResult(success, action, f"Hotkey {'+'.join(keys)}")

            if action == CanonicalAction.COPY:
                success = self._desktop_controller.hotkey("ctrl", "c")
                return ActionResult(success, action, "Copied to clipboard" if success else "Copy failed")

            if action == CanonicalAction.PASTE:
                success = self._desktop_controller.hotkey("ctrl", "v")
                return ActionResult(success, action, "Pasted from clipboard" if success else "Paste failed")

            if action == CanonicalAction.CUT:
                success = self._desktop_controller.hotkey("ctrl", "x")
                return ActionResult(success, action, "Cut selection" if success else "Cut failed")

            if action == CanonicalAction.START_SELECTING:
                if self._selection_manager:
                    self._selection_manager.start_selection(request.target_x, request.target_y)
                return ActionResult(True, action, "Selection started")

            if action == CanonicalAction.STOP_SELECTING:
                if self._selection_manager:
                    self._selection_manager.stop_selection(request.target_x, request.target_y)
                return ActionResult(True, action, "Selection stopped")

            if action == CanonicalAction.SELECT:
                success = self._desktop_controller.hotkey("ctrl", "a")
                return ActionResult(success, action, "Selected all")

            # Navigation & Scrolling
            if action == CanonicalAction.SCROLL_DOWN:
                clicks = request.params.get("clicks", -5)
                success = self._desktop_controller.scroll(clicks)
                return ActionResult(success, action, "Scrolled down" if success else "Scroll failed")

            if action == CanonicalAction.SCROLL_UP:
                clicks = request.params.get("clicks", 5)
                success = self._desktop_controller.scroll(clicks)
                return ActionResult(success, action, "Scrolled up" if success else "Scroll failed")

            # System & Media
            if action == CanonicalAction.VOLUME_UP:
                success = self._desktop_controller.press("volumeup", presses=2)
                return ActionResult(success, action, "Volume up")

            if action == CanonicalAction.VOLUME_DOWN:
                success = self._desktop_controller.press("volumedown", presses=2)
                return ActionResult(success, action, "Volume down")

            if action == CanonicalAction.MUTE:
                success = self._desktop_controller.mute()
                return ActionResult(success, action, "Muted")

            if action == CanonicalAction.SCREENSHOT:
                success = self._desktop_controller.take_screenshot()
                return ActionResult(success, action, "Screenshot captured")

            if action == CanonicalAction.BROWSER_SEARCH:
                app = request.target_phrase or "chrome"
                query = request.text_payload or request.params.get("query", "")
                success = self._desktop_controller.browser_search(app, query)
                return ActionResult(success, action, f"Searched '{query}' in {app}")

            return ActionResult(False, action, f"Unsupported action: {action.value}")

    def _execute_click(self, request: ActionRequest) -> ActionResult:
        """Execute click action at target coordinates or current cursor location."""
        x = request.target_x
        y = request.target_y

        if x is not None and y is not None:
            self._desktop_controller.move_rel(int(x), int(y))

        if request.action == CanonicalAction.RIGHT_CLICK:
            success = self._desktop_controller.click(button="right", clicks=1)
            msg = f"Right clicked at ({x:.1f}, {y:.1f})" if x and y else "Right clicked"
        elif request.action == CanonicalAction.DOUBLE_CLICK:
            success = self._desktop_controller.click(button="left", clicks=2)
            msg = f"Double clicked at ({x:.1f}, {y:.1f})" if x and y else "Double clicked"
        else:
            success = self._desktop_controller.click(button="left", clicks=1)
            msg = f"Clicked at ({x:.1f}, {y:.1f})" if x and y else "Clicked"

        return ActionResult(success, request.action, msg)
