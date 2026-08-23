"""Vision Actions & Desktop Interaction Data Models."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any


@dataclass
class VisualTargetRef:
    """Natural language target reference for visual grounding."""

    target_phrase: str
    element_type: str = "button"  # "button", "link", "input", "text", "checkbox"
    ordinal_index: int = 0
    color_hint: str | None = None
    confidence: float = 1.0
    interaction_mode: str = "ACCESSIBILITY"


@dataclass
class GroundedPoint:
    """Grounded screen coordinate and target metadata."""

    x: int
    y: int
    confidence: float
    text_label: str
    bounding_box: tuple[int, int, int, int]  # (x, y, width, height)


@dataclass
class VisualActionResult:
    """Outcome of a visually grounded desktop action."""

    action_type: str  # "CLICK_AT", "TYPE_AT", "READ_REGION"
    success: bool
    grounded_point: GroundedPoint | None = None
    delta_detected: bool = True
    message: str = ""
    timestamp: float = field(default_factory=time.time)
