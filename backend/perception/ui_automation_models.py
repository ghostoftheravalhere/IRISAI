"""Windows UI Automation Models & Interaction Modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InteractionMode(str, Enum):
    """Interaction execution priority mode for desktop automation."""

    ACCESSIBILITY = "ACCESSIBILITY"
    OCR = "OCR"
    COORDINATE = "COORDINATE"
    HYBRID = "HYBRID"


@dataclass
class AccessibilityElement:
    """Model representing a semantic UI element in the OS accessibility tree."""

    name: str
    role: str  # "Button", "TextBox", "Menu", "CheckBox", "Tab", "ComboBox", etc.
    runtime_id: str = ""
    automation_id: str = ""
    bounding_rectangle: tuple[int, int, int, int] = (0, 0, 0, 0)
    enabled: bool = True
    focused: bool = False
    visible: bool = True
    supports_invoke: bool = True
    supports_value: bool = False
    supports_selection: bool = False
    supports_expand: bool = False
    raw_control: Any | None = None
