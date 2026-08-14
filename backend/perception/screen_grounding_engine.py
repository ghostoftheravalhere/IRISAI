"""Screen Grounding & Bounding Box Coordinate Mapper."""

from __future__ import annotations

from backend.perception.ocr_service import OCREngine, OCRResult
from backend.perception.ui_element_detector import UIElementDetector
from backend.perception.vision_action_models import GroundedPoint, VisualTargetRef
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ScreenGroundingEngine:
    """Maps visual target references to exact (x, y) screen center coordinates."""

    def __init__(self, detector: UIElementDetector | None = None) -> None:
        self._detector = detector or UIElementDetector()

    def ground_target(self, ocr_result: OCRResult, target_ref: VisualTargetRef) -> GroundedPoint | None:
        """Find matching text in OCR results and calculate center coordinates."""
        phrase = target_ref.target_phrase.strip().lower()
        matches = []

        for bbox in ocr_result.boxes:
            if phrase in bbox.text.lower():
                matches.append(bbox)

        if not matches:
            # Fallback to UIElementDetector match
            match = self._detector.find_element(phrase, ocr_result)
            if match:
                return GroundedPoint(
                    x=match.center_x,
                    y=match.center_y,
                    confidence=match.confidence,
                    text_label=match.label,
                    bounding_box=(match.bounding_box.x, match.bounding_box.y, match.bounding_box.width, match.bounding_box.height),
                )
            return None

        # Pick ordinal index match
        idx = min(target_ref.ordinal_index, len(matches) - 1)
        matched_box = matches[idx]

        center_x = matched_box.x + (matched_box.width // 2)
        center_y = matched_box.y + (matched_box.height // 2)

        return GroundedPoint(
            x=center_x,
            y=center_y,
            confidence=matched_box.confidence,
            text_label=matched_box.text,
            bounding_box=(matched_box.x, matched_box.y, matched_box.width, matched_box.height),
        )
