"""Dispatch parsed voice intents to desktop automation actions (DEPRECATED).

DEPRECATED: Preferred authoritative action execution engine is backend.automation.action_engine.ActionEngine.
This module is maintained for backward compatibility with legacy unit tests and API routes.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock

from backend.automation.controller import ApplicationCloseResult, DesktopController
from backend.utils.logger import get_logger
from backend.voice.command_parser import VoiceIntent, VoiceIntentType

logger = get_logger(__name__)

_APP_DISPLAY_NAMES = {
    "chrome": "Chrome",
    "notepad": "Notepad",
    "edge": "Edge",
    "settings": "Settings",
}


@dataclass(frozen=True)
class AutomationResult:
    """Result of a desktop automation dispatch."""

    success: bool
    intent: VoiceIntentType
    message: str


class AutomationDispatcher:
    """Route supported voice intents to reusable automation primitives."""

    def __init__(
        self,
        desktop_controller: DesktopController,
        skill_registry: Any | None = None,
    ) -> None:
        self._desktop_controller = desktop_controller
        self._skill_registry = skill_registry
        self._lock = RLock()

    def dispatch(self, voice_intent: VoiceIntent) -> AutomationResult:
        """Execute a desktop action for a parsed voice intent."""
        with self._lock:
            intent = voice_intent.intent
            if intent == VoiceIntentType.NO_INTENT:
                return AutomationResult(False, intent, "Unknown command.")

            if intent in {VoiceIntentType.OPEN_APPLICATION, VoiceIntentType.OPEN_CHROME, VoiceIntentType.OPEN_NOTEPAD}:
                return self._dispatch_open(voice_intent)

            if intent == VoiceIntentType.CLOSE_WINDOW:
                success = self._desktop_controller.close_window()
                message = "Window closed" if success else "Failed to close window"
                logger.info("Voice close window success=%s", success)
                return AutomationResult(success, intent, message)

            if intent == VoiceIntentType.BROWSER_SEARCH:
                app = voice_intent.target or "chrome"
                query = voice_intent.query or voice_intent.text
                success = self._desktop_controller.browser_search(app, query)
                message = f"Searched '{query}' in {app}" if success else f"Failed search in {app}"
                logger.info("Voice browser search result: %s success=%s", message, success)
                return AutomationResult(success, intent, message)

            if intent == VoiceIntentType.HOTKEY:
                keys = voice_intent.params.get("keys", ["ctrl", "l"]) if voice_intent.params else ["ctrl", "l"]
                success = self._desktop_controller.hotkey(*keys)
                return AutomationResult(success, intent, f"Hotkey {'+'.join(keys)}")

            if intent == VoiceIntentType.TYPE_TEXT:
                text_to_type = voice_intent.query or (voice_intent.params.get("text", "") if voice_intent.params else voice_intent.text)
                success = self._desktop_controller.type_text(text_to_type)
                return AutomationResult(success, intent, f"Typed text '{text_to_type}'")

            if intent == VoiceIntentType.PRESS_KEY:
                key = voice_intent.params.get("key", "enter") if voice_intent.params else "enter"
                success = self._desktop_controller.press(key)
                return AutomationResult(success, intent, f"Pressed key '{key}'")

            if intent == VoiceIntentType.WAIT_FOR_WINDOW:
                target = voice_intent.target or "chrome"
                timeout = voice_intent.params.get("timeout_sec", 3.0) if voice_intent.params else 3.0
                success = self._desktop_controller.wait_for_window(target, timeout_sec=timeout)
                return AutomationResult(success, intent, f"Wait for window '{target}' success={success}")

            if intent == VoiceIntentType.ACTIVATE_WINDOW:
                target = voice_intent.target or "chrome"
                success = self._desktop_controller.activate_window(target)
                return AutomationResult(success, intent, f"Activate window '{target}' success={success}")

            if intent == VoiceIntentType.VERIFY_WINDOW_ACTIVE:
                target = voice_intent.target or "chrome"
                active = self._desktop_controller.wait_for_window_active(target, timeout_sec=3.0)
                return AutomationResult(active, intent, f"Verify window active '{target}' success={active}")

            if intent == VoiceIntentType.CLOSE_APPLICATION:
                return self._dispatch_close(voice_intent)

            handlers: dict[VoiceIntentType, tuple[Callable[[], bool], str, str]] = {
                VoiceIntentType.SCROLL_DOWN: (
                    lambda: self._desktop_controller.scroll(-5),
                    "Scrolled down",
                    "Scroll failed",
                ),
                VoiceIntentType.SCROLL_UP: (
                    lambda: self._desktop_controller.scroll(5),
                    "Scrolled up",
                    "Scroll failed",
                ),
                VoiceIntentType.VOLUME_UP: (
                    lambda: self._desktop_controller.press("volumeup", presses=2),
                    "Volume up",
                    "Volume up failed",
                ),
                VoiceIntentType.VOLUME_DOWN: (
                    lambda: self._desktop_controller.press("volumedown", presses=2),
                    "Volume down",
                    "Volume down failed",
                ),
                VoiceIntentType.MUTE: (
                    self._desktop_controller.mute,
                    "Muted",
                    "Mute failed",
                ),
                VoiceIntentType.COPY: (
                    lambda: self._desktop_controller.hotkey("ctrl", "c"),
                    "Copied",
                    "Copy failed",
                ),
                VoiceIntentType.PASTE: (
                    lambda: self._desktop_controller.hotkey("ctrl", "v"),
                    "Pasted",
                    "Paste failed",
                ),
                VoiceIntentType.SELECT_ALL: (
                    lambda: self._desktop_controller.hotkey("ctrl", "a"),
                    "Selected all",
                    "Select all failed",
                ),
                VoiceIntentType.MINIMIZE_WINDOW: (
                    lambda: self._desktop_controller.hotkey("win", "down"),
                    "Window minimized",
                    "Minimize failed",
                ),
                VoiceIntentType.TAKE_SCREENSHOT: (
                    self._desktop_controller.take_screenshot,
                    "Screenshot saved",
                    "Screenshot failed",
                ),
            }

            handler_entry = handlers.get(intent)
            if handler_entry is None:
                logger.warning("No automation handler registered for intent: %s", intent.value)
                return AutomationResult(False, intent, "Unknown command.")

            handler, ok_message, fail_message = handler_entry
            success = handler()
            message = ok_message if success else fail_message
            logger.info("Voice automation result: %s success=%s", intent.value, success)
            return AutomationResult(success, intent, message)

    def _dispatch_open(self, voice_intent: VoiceIntent) -> AutomationResult:
        """Open an application and return a user-facing status message."""
        intent = voice_intent.intent
        target = (voice_intent.target or "").strip().lower()
        display = self._display_name(target) if target else None

        if intent == VoiceIntentType.OPEN_CHROME or target == "chrome":
            success = self._desktop_controller.open_chrome()
            display = "Chrome"
        elif intent == VoiceIntentType.OPEN_NOTEPAD or target == "notepad":
            success = self._desktop_controller.open_notepad()
            display = "Notepad"
        elif target == "edge":
            success = self._desktop_controller.open_edge()
            display = "Edge"
        elif target in ("settings", "setting", "windows settings", "system settings"):
            success = self._desktop_controller.open_settings()
            display = "Settings"
        elif target:
            success = self._desktop_controller.open_application(target)
            display = target.title()
        else:
            logger.warning("Unsupported open application target: %s", target or intent.value)
            return AutomationResult(False, intent, "Unsupported application.")

        message = f"{display} opened" if success else f"Failed to open {display}"
        return AutomationResult(success, intent, message)

    def _dispatch_close(self, voice_intent: VoiceIntent) -> AutomationResult:
        """Close a named app by process, or the active window when no app is named."""
        intent = voice_intent.intent
        target = (voice_intent.target or "").strip().lower()

        # Parser emits CLOSE_APPLICATION with target=window for bare "Close".
        if not target or target == "window":
            success = self._desktop_controller.close_window()
            message = "Window closed" if success else "Failed to close window"
            logger.info("Voice close window (via CLOSE_APPLICATION) success=%s", success)
            return AutomationResult(success, intent, message)

        result = self._desktop_controller.close_application(target)
        message = self._close_message(target, result)
        logger.info(
            "Voice close application target=%s status=%s success=%s",
            target,
            result.status,
            result.success,
        )
        return AutomationResult(result.success, intent, message)

    def _open_application(self, voice_intent: VoiceIntent) -> bool:
        """Open an application from intent type and/or target."""
        result = self._dispatch_open(voice_intent)
        return result.success

    def _close_application(self, voice_intent: VoiceIntent) -> bool:
        """Close helper kept for tests/back-compat; prefer ``_dispatch_close``."""
        result = self._dispatch_close(voice_intent)
        return result.success

    @staticmethod
    def _display_name(target: str) -> str:
        return _APP_DISPLAY_NAMES.get(target, target.capitalize() if target else "Application")

    def _close_message(self, target: str, result: ApplicationCloseResult) -> str:
        display = self._display_name(target)
        if result.status == "closed":
            return f"{display} closed"
        if result.status == "not_running":
            return f"{display} is not running."
        if result.status == "unsupported":
            return f"Unsupported application: {display}"
        return f"Failed to close {display}"
