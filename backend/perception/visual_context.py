"""Visual Context Snapshot Model & Generator."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Sequence

from backend.perception.ocr_service import OCRBoundingBox, OCRResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VisualContext:
    """Snapshot model representing visual perception state."""

    app_title: str = "System"
    visible_text: str = ""
    element_count: int = 0
    bounding_boxes: list[OCRBoundingBox] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    privacy_redacted: bool = False

    def to_dict() -> dict[str, Any]:
        return {
            "app_title": self.app_title,
            "visible_text": self.visible_text,
            "element_count": self.element_count,
            "timestamp": self.timestamp,
            "privacy_redacted": self.privacy_redacted,
        }


class VisualContextGenerator:
    """Generates structured visual context from window bounds and OCR results."""

    def build_context(self, app_title: str, ocr_result: OCRResult) -> VisualContext:
        """Construct a VisualContext snapshot."""
        boxes = ocr_result.boxes if ocr_result else []
        full_text = ocr_result.full_text if ocr_result else ""

        return VisualContext(
            app_title=app_title or "System",
            visible_text=full_text,
            element_count=len(boxes),
            bounding_boxes=boxes,
            timestamp=time.time(),
            privacy_redacted=True,
        )
