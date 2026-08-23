"""Vision Intelligence Domain Events."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any


@dataclass(frozen=True)
class ScreenCapturedEvent:
    """Event emitted when a screen or active window frame is captured."""

    timestamp: float = field(default_factory=time.time)
    window_title: str = ""
    width: int = 0
    height: int = 0
    region: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class OCRCompletedEvent:
    """Event emitted when OCR text extraction completes."""

    text_count: int
    duration_ms: float
    confidence: float
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class VisualContextUpdatedEvent:
    """Event emitted when active visual context updates."""

    app_title: str
    element_count: int
    text_snippet: str
    timestamp: float = field(default_factory=time.time)
