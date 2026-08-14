"""Clipboard Intelligence Subsystem for Cross-App Data Verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
import time

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ClipboardItem:
    """Represents a clipboard text entry and its source metadata."""

    text: str
    source_app: str = "Unknown"
    timestamp: float = field(default_factory=time.time)


class ClipboardIntelligence:
    """Manages clipboard history, ownership tracking, and cross-application data verification."""

    def __init__(self) -> None:
        self._history: list[ClipboardItem] = []
        self._lock = RLock()

    def copy(self, text: str, source_app: str = "System") -> bool:
        """Store text into clipboard with source app attribution."""
        with self._lock:
            item = ClipboardItem(text=text, source_app=source_app)
            self._history.append(item)
            logger.info("ClipboardIntelligence copy from '%s': %d chars", source_app, len(text))
            return True

    def paste(self) -> str:
        """Get latest clipboard content."""
        with self._lock:
            if self._history:
                return self._history[-1].text
            return ""

    def restore_previous(self) -> bool:
        """Pop latest clipboard item and restore previous content."""
        with self._lock:
            if len(self._history) > 1:
                popped = self._history.pop()
                logger.info("ClipboardIntelligence restored previous item (popped %d chars)", len(popped.text))
                return True
            return False

    def get_history(self) -> list[ClipboardItem]:
        """Return clipboard history stack."""
        with self._lock:
            return list(self._history)
