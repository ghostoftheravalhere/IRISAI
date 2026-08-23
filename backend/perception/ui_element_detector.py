"""UI Element Detector & Coordinate Grounding Service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from backend.perception.ocr_service import OCRBoundingBox, OCRResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class UIElementMatch:
    """Target UI element matched by phrase query."""

    label: str
    center_x: int
    center_y: int
    bounding_box: OCRBoundingBox
    confidence: float


class UIElementDetector:
    """Detects UI elements and maps target label phrases to screen coordinates."""

    def find_element(self, query: str, ocr_result: OCRResult) -> UIElementMatch | None:
        """Find the bounding box matching a label phrase query."""
        if not query or not ocr_result or not ocr_result.boxes:
            return None

        target = query.strip().lower()
        best_box: OCRBoundingBox | None = None
        best_score = 0.0

        for box in ocr_result.boxes:
            text_clean = box.text.strip().lower()
            if text_clean == target:
                return UIElementMatch(
                    label=box.text,
                    center_x=box.center_x,
                    center_y=box.center_y,
                    bounding_box=box,
                    confidence=1.0,
                )
            if target in text_clean or text_clean in target:
                score = len(target) / max(1, len(text_clean))
                if score > best_score:
                    best_score = score
                    best_box = box

        if best_box is not None and best_score >= 0.5:
            return UIElementMatch(
                label=best_box.text,
                center_x=best_box.center_x,
                center_y=best_box.center_y,
                bounding_box=best_box,
                confidence=best_score,
            )

        return None
