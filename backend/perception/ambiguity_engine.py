"""Candidate ranking and ambiguity resolution engine for screen and context targets."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import math
from typing import Any, Sequence

from backend.perception.ocr_service import OCRResult
from backend.perception.ui_automation_engine import AccessibilityElement, UIAutomationEngine
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class CandidateMatch:
    """Scored target candidate from screen, UIA element tree, or context."""

    label: str
    x: float
    y: float
    confidence_score: float
    match_reason: str
    element_type: str = "button"
    raw_element: Any | None = None


@dataclass(frozen=True)
class AmbiguityResolution:
    """Consolidated outcome of ambiguity analysis."""

    classification: str  # "HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE", "MULTIPLE_CANDIDATES", "NO_MATCH"
    best_candidate: CandidateMatch | None
    candidates: tuple[CandidateMatch, ...]
    prompt_message: str | None = None


class AmbiguityEngine:
    """Evaluates target phrase against UI elements, active window text, and gaze proximity."""

    def __init__(
        self,
        uia_engine: UIAutomationEngine | None = None,
        high_threshold: float = 0.85,
        medium_threshold: float = 0.55,
    ) -> None:
        self._uia_engine = uia_engine or UIAutomationEngine()
        self._high_threshold = high_threshold
        self._medium_threshold = medium_threshold

    def resolve_candidates(
        self,
        target_phrase: str,
        active_app: str | None = None,
        gaze_x: float | None = None,
        gaze_y: float | None = None,
        available_elements: Sequence[AccessibilityElement] | Sequence[dict[str, Any]] | None = None,
        ocr_result: OCRResult | None = None,
    ) -> AmbiguityResolution:
        """Score and rank candidates for a user target phrase."""
        phrase = (target_phrase or "").strip().lower()
        if not phrase:
            return AmbiguityResolution("NO_MATCH", None, ())

        scored_candidates: list[CandidateMatch] = []

        # 1. Evaluate explicit element list or UIA engine
        elements = available_elements or self._get_uia_elements()
        for elem in elements:
            label, x, y, elem_type = self._extract_element_info(elem)
            if not label:
                continue

            score, reason = self._calculate_score(phrase, label, active_app, gaze_x, gaze_y, x, y)
            if score > 0.30:
                scored_candidates.append(
                    CandidateMatch(
                        label=label,
                        x=x,
                        y=y,
                        confidence_score=score,
                        match_reason=reason,
                        element_type=elem_type,
                        raw_element=elem,
                    )
                )

        # 2. Evaluate OCR boxes if provided
        if ocr_result and ocr_result.boxes:
            for box in ocr_result.boxes:
                label = box.text.strip()
                if not label:
                    continue
                center_x = float(box.x + box.width // 2)
                center_y = float(box.y + box.height // 2)
                score, reason = self._calculate_score(phrase, label, active_app, gaze_x, gaze_y, center_x, center_y)
                if score > 0.30:
                    scored_candidates.append(
                        CandidateMatch(
                            label=label,
                            x=center_x,
                            y=center_y,
                            confidence_score=score,
                            match_reason=f"OCR {reason}",
                            element_type="text_label",
                            raw_element=box,
                        )
                    )

        # Sort candidates descending by confidence_score
        scored_candidates.sort(key=lambda c: c.confidence_score, reverse=True)
        candidates_tuple = tuple(scored_candidates)

        if not candidates_tuple:
            return AmbiguityResolution("NO_MATCH", None, ())

        top_match = candidates_tuple[0]

        # Check for multiple close candidates
        close_matches = [c for c in candidates_tuple if c.confidence_score >= self._medium_threshold]
        if len(close_matches) > 1 and abs(close_matches[0].confidence_score - close_matches[1].confidence_score) < 0.15:
            labels_str = ", ".join(f"{i+1}. {c.label}" for i, c in enumerate(close_matches[:3]))
            prompt = f"I found multiple matches: {labels_str}. Which one do you want?"
            return AmbiguityResolution("MULTIPLE_CANDIDATES", top_match, candidates_tuple, prompt_message=prompt)

        if top_match.confidence_score >= self._high_threshold:
            return AmbiguityResolution("HIGH_CONFIDENCE", top_match, candidates_tuple)

        if top_match.confidence_score >= self._medium_threshold:
            prompt = f"I found '{top_match.label}'. Do you want me to open it?"
            return AmbiguityResolution("MEDIUM_CONFIDENCE", top_match, candidates_tuple, prompt_message=prompt)

        return AmbiguityResolution("NO_MATCH", top_match, candidates_tuple)

    def _calculate_score(
        self,
        phrase: str,
        label: str,
        active_app: str | None,
        gaze_x: float | None,
        gaze_y: float | None,
        elem_x: float,
        elem_y: float,
    ) -> tuple[float, str]:
        """Compute weighted confidence score for target matching."""
        label_lower = label.lower()

        # Fuzzy string similarity & token overlap
        if phrase == label_lower:
            fuzzy_score = 1.0
        else:
            matcher = SequenceMatcher(None, phrase, label_lower)
            ratio = matcher.ratio()
            phrase_tokens = set(t for t in phrase.split() if len(t) > 2)
            label_tokens = set(t for t in label_lower.split() if len(t) > 2)
            if phrase_tokens and phrase_tokens.issubset(label_tokens):
                token_score = 0.88
            elif phrase_tokens and label_tokens:
                token_score = len(phrase_tokens & label_tokens) / len(phrase_tokens) * 0.75
            else:
                token_score = 0.0
            fuzzy_score = max(ratio, token_score)

        if fuzzy_score < 0.75 and phrase_tokens and label_tokens and not (phrase_tokens & label_tokens):
            return 0.0, "No token overlap"

        if fuzzy_score < 0.20:
            return 0.0, "Insufficient text similarity"

        # Context relevance
        if active_app and active_app.lower() in label_lower:
            context_score = 1.0
        elif active_app is None:
            context_score = 0.85
        else:
            context_score = 0.5

        # Spatial gaze proximity
        if gaze_x is not None and gaze_y is not None:
            dist = math.hypot(gaze_x - elem_x, gaze_y - elem_y)
            proximity_score = math.exp(-dist / 300.0)
        else:
            proximity_score = 0.85

        total_score = (0.50 * fuzzy_score) + (0.30 * context_score) + (0.20 * proximity_score)
        reason = f"Fuzzy={fuzzy_score:.2f}, Context={context_score:.2f}, Proximity={proximity_score:.2f}"
        return min(1.0, total_score), reason

    def _get_uia_elements(self) -> list[Any]:
        try:
            return self._uia_engine.find_all()
        except Exception:
            return []

    def _extract_element_info(self, elem: Any) -> tuple[str, float, float, str]:
        if isinstance(elem, dict):
            return (
                str(elem.get("name") or elem.get("label") or ""),
                float(elem.get("x") or 0.0),
                float(elem.get("y") or 0.0),
                str(elem.get("type") or "button"),
            )
        if isinstance(elem, AccessibilityElement):
            return (
                elem.name or "",
                float(elem.bounding_box[0] + elem.bounding_box[2] // 2) if hasattr(elem, "bounding_box") and elem.bounding_box else 0.0,
                float(elem.bounding_box[1] + elem.bounding_box[3] // 2) if hasattr(elem, "bounding_box") and elem.bounding_box else 0.0,
                elem.role or "button",
            )
        name = getattr(elem, "name", "") or getattr(elem, "label", "") or ""
        x = float(getattr(elem, "x", 0.0))
        y = float(getattr(elem, "y", 0.0))
        role = getattr(elem, "role", "button")
        return name, x, y, role
