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
        cursor_controller: Any | None = None,
        eye_calibration: Any | None = None,
        eye_config: Any | None = None,
    ) -> None:
        self._desktop_controller = desktop_controller
        self._skill_registry = skill_registry
        self._cursor_controller = cursor_controller
        self._eye_calibration = eye_calibration
        self._eye_config = eye_config
        self._lock = RLock()

    def set_eye_services(
        self,
        cursor_controller: Any | None = None,
        eye_calibration: Any | None = None,
        eye_config: Any | None = None,
    ) -> None:
        with self._lock:
            if cursor_controller is not None:
                self._cursor_controller = cursor_controller
            if eye_calibration is not None:
                self._eye_calibration = eye_calibration
            if eye_config is not None:
                self._eye_config = eye_config

    def dispatch(self, voice_intent: VoiceIntent) -> AutomationResult:
        """Execute a desktop action for a parsed voice intent."""
        with self._lock:
            intent = voice_intent.intent
            if intent == VoiceIntentType.NO_INTENT:
                return AutomationResult(False, intent, "Unknown command.")

            if intent == VoiceIntentType.START_CURSOR_CONTROL:
                return self._dispatch_start_cursor_control(voice_intent)

            if intent == VoiceIntentType.STOP_CURSOR_CONTROL:
                return self._dispatch_stop_cursor_control(voice_intent)

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
        """Open an application using DesktopAppResolver and return a user-facing status message."""
        intent = voice_intent.intent
        target = (voice_intent.target or "").strip().lower()
        if not target:
            if intent == VoiceIntentType.OPEN_CHROME:
                target = "chrome"
            elif intent == VoiceIntentType.OPEN_NOTEPAD:
                target = "notepad"
            else:
                logger.warning("Unsupported open application target: empty target")
                return AutomationResult(False, intent, "Unsupported application.")

        from backend.automation.app_resolver import app_resolver
        resolved = app_resolver.resolve_app_target(target)
        canonical = resolved.canonical_name if resolved and resolved.found else target.title()

        if (intent == VoiceIntentType.OPEN_CHROME or target == "chrome") and hasattr(self._desktop_controller, "open_chrome") and type(self._desktop_controller) is not DesktopController:
            success = self._desktop_controller.open_chrome()
        elif (intent == VoiceIntentType.OPEN_NOTEPAD or target == "notepad") and hasattr(self._desktop_controller, "open_notepad") and type(self._desktop_controller) is not DesktopController:
            success = self._desktop_controller.open_notepad()
        elif target == "edge" and hasattr(self._desktop_controller, "open_edge") and type(self._desktop_controller) is not DesktopController:
            success = self._desktop_controller.open_edge()
        else:
            success = self._desktop_controller.open_application(target)

        if target in _APP_DISPLAY_NAMES:
            message = f"{_APP_DISPLAY_NAMES[target]} opened" if success else f"Failed to open {_APP_DISPLAY_NAMES[target]}"
        else:
            message = f"{canonical} opened." if success else f"Sir, I couldn't find {canonical} on this computer."

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

        from backend.automation.app_resolver import app_resolver
        resolved = app_resolver.resolve_running_app(target)
        logger.info(
            "\n" + "=" * 50 +
            "\nLIVE CLOSE REQUEST" +
            f"\ntarget = {target}" +
            f"\nresolver = DesktopAppResolver" +
            f"\nresolved application = {resolved.name}" +
            f"\nmatched = {resolved.matched}" +
            f"\nprocesses = {resolved.process_names}" +
            f"\nPIDs = {resolved.pids}" +
            "\n" + "=" * 50 + "\n"
        )

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
        if not target:
            return "Application"
        if target in _APP_DISPLAY_NAMES:
            return _APP_DISPLAY_NAMES[target]
        from backend.automation.app_resolver import app_resolver
        return app_resolver.get_canonical_name(target)

    def _close_message(self, target: str, result: ApplicationCloseResult) -> str:
        display = self._display_name(target)
        if result.status == "closed":
            return f"{display} closed"
        if result.status == "not_running":
            return f"{display} is not running."
        if result.status == "unsupported":
            return f"Unsupported application: {display}"
        return f"Failed to close {display}"

    def _dispatch_start_cursor_control(self, voice_intent: VoiceIntent) -> AutomationResult:
        """Enable existing eye CursorController respecting calibration quality and safety gates."""
        intent = voice_intent.intent

        if self._eye_calibration is not None:
            progress = self._eye_calibration.get_progress()
            if not progress.complete:
                msg = "Calibration must be complete before enabling cursor control."
                logger.info("Voice start cursor control blocked: calibration incomplete")
                return AutomationResult(False, intent, msg)

            quality = progress.quality
            threshold = getattr(self._eye_config, "calibration_quality_threshold", 0.085) if self._eye_config else 0.085
            if quality is None or quality.recommend_recalibration or (quality.score is not None and quality.score < threshold) or (quality.rmse is not None and quality.rmse > threshold):
                msg = "Calibration quality is too low for reliable cursor control. Recalibrate, then try enabling cursor again."
                logger.info("Voice start cursor control blocked: low calibration quality")
                return AutomationResult(False, intent, msg)

        if self._cursor_controller is not None:
            self._cursor_controller.enable()
            logger.info("Voice start cursor control: enabled existing CursorController")
            return AutomationResult(True, intent, "Cursor control enabled.")

        logger.warning("Voice start cursor control: CursorController unavailable")
        return AutomationResult(False, intent, "Cursor controller unavailable.")

    def _dispatch_stop_cursor_control(self, voice_intent: VoiceIntent) -> AutomationResult:
        """Immediately disable existing eye CursorController without stopping camera or face tracking."""
        intent = voice_intent.intent
        if self._cursor_controller is not None:
            self._cursor_controller.disable()
            logger.info("Voice stop cursor control: disabled existing CursorController immediately")
        else:
            logger.warning("Voice stop cursor control: CursorController unavailable")

        return AutomationResult(True, intent, "Cursor control disabled.")
