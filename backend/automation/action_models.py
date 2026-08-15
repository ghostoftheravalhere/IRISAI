"""Canonical action models and vocabulary definitions for IRIS AI V4 ActionEngine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CanonicalAction(str, Enum):
    """Normalized canonical action vocabulary for all input modalities."""

    # Mouse & Pointing
    CLICK = "CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    RIGHT_CLICK = "RIGHT_CLICK"
    DRAG_START = "DRAG_START"
    DRAG_END = "DRAG_END"

    # Text & Selection
    SELECT = "SELECT"
    START_SELECTING = "START_SELECTING"
    STOP_SELECTING = "STOP_SELECTING"
    COPY = "COPY"
    PASTE = "PASTE"
    CUT = "CUT"
    TYPE_TEXT = "TYPE_TEXT"
    PRESS_KEY = "PRESS_KEY"
    HOTKEY = "HOTKEY"

    # Navigation & Scrolling
    SCROLL_UP = "SCROLL_UP"
    SCROLL_DOWN = "SCROLL_DOWN"

    # Window & Application Management
    OPEN_APPLICATION = "OPEN_APPLICATION"
    OPEN_CHAT = "OPEN_CHAT"
    CLOSE_WINDOW = "CLOSE_WINDOW"
    CLOSE_APPLICATION = "CLOSE_APPLICATION"
    MINIMIZE_WINDOW = "MINIMIZE_WINDOW"
    MAXIMIZE_WINDOW = "MAXIMIZE_WINDOW"
    SWITCH_WINDOW = "SWITCH_WINDOW"
    WAIT_FOR_WINDOW = "WAIT_FOR_WINDOW"
    ACTIVATE_WINDOW = "ACTIVATE_WINDOW"
    VERIFY_WINDOW_ACTIVE = "VERIFY_WINDOW_ACTIVE"

    # System & Media
    VOLUME_UP = "VOLUME_UP"
    VOLUME_DOWN = "VOLUME_DOWN"
    MUTE = "MUTE"
    SCREENSHOT = "SCREENSHOT"
    BROWSER_SEARCH = "BROWSER_SEARCH"

    # Fallback
    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True)
class ActionRequest:
    """Normalized action request emitted by voice, gaze, or dialogue subsystems."""

    action: CanonicalAction
    source_modality: str = "voice"  # "voice", "gaze", "blink", "multimodal", "ui"
    target_phrase: str | None = None
    target_x: float | None = None
    target_y: float | None = None
    text_payload: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    requires_confirmation: bool = False


@dataclass(frozen=True)
class ActionResult:
    """Outcome of canonical ActionEngine execution."""

    success: bool
    action: CanonicalAction
    message: str
    params: dict[str, Any] = field(default_factory=dict)
