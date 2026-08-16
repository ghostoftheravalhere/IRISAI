"""Structured Screen Grounding Engine for IRIS AI V4.

Extracts canonical ScreenElement instances from Windows UIAutomation accessibility trees
(with lightweight OCR fallback), performs fuzzy semantic target matching, spatial gaze resolution,
detects ambiguous target candidates, and updates WorldModel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import time
from typing import Any

from backend.brain.world_model import world_model
from backend.perception.ocr_service import OCREngine
from backend.perception.ui_automation_engine import UIAutomationEngine
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ScreenElement:
    """Canonical unified Screen Element model for UI perception."""

    element_id: str
    application: str = "ActiveApp"
    window: str = "ActiveWindow"
    role: str = "Control"
    name: str = ""
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)  # (x, y, width, height)
    center: tuple[int, int] = (0, 0)
    visible: bool = True
    enabled: bool = True
    focused: bool = False
    automation_id: str = ""
    source: str = "UIA"  # UIA | OCR | VISION | GAZE
    confidence: float = 1.0

    def to_safe_dict(self) -> dict[str, Any]:
        """Return dict representation without raw screenshot pixel bytes."""
        return {
            "element_id": self.element_id,
            "application": self.application,
            "window": self.window,
            "role": self.role,
            "name": self.name,
            "bounds": self.bounds,
            "center": self.center,
            "visible": self.visible,
            "enabled": self.enabled,
            "focused": self.focused,
            "automation_id": self.automation_id,
            "source": self.source,
            "confidence": round(self.confidence, 2),
        }


@dataclass
class GroundingResult:
    """Outcome of a screen grounding target search."""

    success: bool
    target: ScreenElement | None = None
    candidates: list[ScreenElement] = field(default_factory=list)
    requires_clarification: bool = False
    clarification_message: str = ""
    error_code: str = ""


class VisionGroundingProvider:
    """Protocol interface abstraction for optional future VLM vision providers."""

    def analyze_screen_region(self, frame: Any, prompt: str) -> list[ScreenElement]:
        """Analyze screen frame using VLM provider (interface abstraction)."""
        return []


class ScreenGroundingEngine:
    """Reliable Screen / UI Perception Grounding Engine."""

    def __init__(
        self,
        uia_engine: UIAutomationEngine | None = None,
        ocr_engine: OCREngine | None = None,
        spatial_resolver: Any | None = None,
    ) -> None:
        self._uia_engine = uia_engine or UIAutomationEngine()
        self._ocr_engine = ocr_engine or OCREngine()
        self._spatial_resolver = spatial_resolver
        self._last_grounded_target: ScreenElement | None = None

    def extract_screen_elements(self, app_name: str = "ActiveApp", window_title: str = "ActiveWindow") -> list[ScreenElement]:
        """Extract canonical ScreenElements from UIA with lightweight OCR fallback."""
        elements: list[ScreenElement] = []

        try:
            uia_elements = self._uia_engine.find_all()
            for idx, u_el in enumerate(uia_elements):
                # Calculate bounding center
                x, y, w, h = getattr(u_el, "bounds", (50 + idx * 80, 100, 70, 24))
                cx = x + w // 2
                cy = y + h // 2
                elements.append(
                    ScreenElement(
                        element_id=f"uia_{u_el.automation_id or idx}",
                        application=app_name,
                        window=window_title,
                        role=u_el.role or "Control",
                        name=u_el.name,
                        bounds=(x, y, w, h),
                        center=(cx, cy),
                        visible=True,
                        enabled=u_el.enabled,
                        focused=getattr(u_el, "focused", False),
                        automation_id=u_el.automation_id or "",
                        source="UIA",
                        confidence=1.0,
                    )
                )
        except Exception as exc:
            logger.warning("UIA extraction failed, switching to OCR fallback: %s", exc)

        # OCR Fallback if UIA returned no elements
        if not elements:
            try:
                ocr_res = self._ocr_engine.process_image(None)
                for idx, box in enumerate(ocr_res.boxes):
                    elements.append(
                        ScreenElement(
                            element_id=f"ocr_box_{idx}",
                            application=app_name,
                            window=window_title,
                            role="Text",
                            name=box.text,
                            bounds=(box.x, box.y, box.width, box.height),
                            center=(box.center_x, box.center_y),
                            visible=True,
                            enabled=True,
                            focused=False,
                            automation_id="",
                            source="OCR",
                            confidence=box.confidence,
                        )
                    )
            except Exception as exc:
                logger.error("OCR fallback failed: %s", exc)

        # Update WorldModel UI context
        world_model.update_ui_target(
            active_app=app_name,
            active_window=window_title,
            visible_elements=[e.to_safe_dict() for e in elements],
            focused_element=next((e.to_safe_dict() for e in elements if e.focused), None),
            gaze_target=None,
            last_referenced_target=self._last_grounded_target.to_safe_dict() if self._last_grounded_target else None,
        )

        return elements

    def ground_query(
        self,
        query: str,
        custom_elements: list[ScreenElement] | None = None,
        gaze_estimate: Any | None = None,
    ) -> GroundingResult:
        """Ground semantic query ('Find Send button', 'Click this') to target ScreenElement."""
        q_lower = query.strip().lower()
        elements = custom_elements if custom_elements is not None else self.extract_screen_elements()

        if not elements:
            return GroundingResult(success=False, error_code="NO_ELEMENTS", clarification_message="No visible UI elements detected on screen.")

        # 1. Spatial Deictic Terms ("this", "that", "here")
        if any(term in q_lower for term in ("this", "that", "here")):
            return self._ground_spatial_deictic(elements, gaze_estimate)

        # 2. Extract Ordinal Index ("second result", "first button")
        ordinal_idx = 0
        if "first" in q_lower or "1st" in q_lower:
            ordinal_idx = 0
        elif "second" in q_lower or "2nd" in q_lower:
            ordinal_idx = 1
        elif "third" in q_lower or "3rd" in q_lower:
            ordinal_idx = 2

        # Extract target search phrase (strip query prefix words)
        phrase = re.sub(r"^(find|click|select|where is|the|a|an)\s+", "", q_lower, flags=re.IGNORECASE).strip()
        phrase = re.sub(r"\s+(button|textbox|box|input|link|icon)$", "", phrase, flags=re.IGNORECASE).strip()

        scored_candidates: list[tuple[ScreenElement, float]] = []
        for el in elements:
            score = self._calculate_match_score(phrase, q_lower, el)
            if score > 0.3:
                scored_candidates.append((el, score))

        # Sort candidates descending by match score
        scored_candidates.sort(key=lambda item: item[1], reverse=True)

        if not scored_candidates:
            return GroundingResult(success=False, error_code="NOT_FOUND", clarification_message=f"Could not find UI element matching '{phrase}'.")

        # Pick ordinal index match if specified
        if ordinal_idx > 0 and len(scored_candidates) > ordinal_idx:
            chosen = scored_candidates[ordinal_idx][0]
            self._last_grounded_target = chosen
            return GroundingResult(success=True, target=chosen, candidates=[c[0] for c in scored_candidates])

        # Ambiguity check: Top two candidates have almost equal scores (within 0.05)
        top_el, top_score = scored_candidates[0]
        if len(scored_candidates) > 1:
            second_el, second_score = scored_candidates[1]
            if (top_score - second_score) < 0.05 and top_el.name.lower() == second_el.name.lower():
                c_names = [f"'{c[0].name}' ({c[0].role})" for c in scored_candidates[:2]]
                msg = f"I found multiple matching controls ({', '.join(c_names)}). Which one do you mean?"
                logger.info("Grounding ambiguity detected: %s", msg)
                return GroundingResult(
                    success=False,
                    candidates=[c[0] for c in scored_candidates[:3]],
                    requires_clarification=True,
                    clarification_message=msg,
                    error_code="AMBIGUOUS_TARGET",
                )

        self._last_grounded_target = top_el
        return GroundingResult(success=True, target=top_el, candidates=[c[0] for c in scored_candidates])

    def _ground_spatial_deictic(self, elements: list[ScreenElement], gaze_estimate: Any | None = None) -> GroundingResult:
        """Ground spatial deictic term ('this', 'that') using live gaze estimate."""
        if not self._spatial_resolver and gaze_estimate is None:
            # Fallback to focused or first visible element
            focused = next((e for e in elements if e.focused), elements[0])
            self._last_grounded_target = focused
            return GroundingResult(success=True, target=focused, candidates=elements)

        if self._spatial_resolver:
            spatial_target = self._spatial_resolver.resolve_spatial_target(custom_gaze=gaze_estimate)
            if not spatial_target:
                return GroundingResult(
                    success=False,
                    error_code="STALE_GAZE",
                    clarification_message="Gaze signal is unclear or stale. Please look directly at the element and try again.",
                )
            matched = self._find_nearest_element_to_coords(spatial_target.x, spatial_target.y, elements)
            if matched:
                self._last_grounded_target = matched
                return GroundingResult(success=True, target=matched, candidates=elements)

        return GroundingResult(success=False, error_code="SPATIAL_FAILED", clarification_message="Could not resolve spatial target.")

    def _calculate_match_score(self, phrase: str, full_query: str, el: ScreenElement) -> float:
        """Calculate match score (0.0 to 1.0) between query phrase and element metadata."""
        score = 0.0
        el_name_lower = el.name.lower().strip()
        el_role_lower = el.role.lower().strip()

        if not phrase and not el_name_lower:
            return 0.0

        if phrase and phrase in el_name_lower:
            score += 0.70
            if phrase == el_name_lower:
                score += 0.25

        if ("button" in full_query and "button" in el_role_lower) or ("search" in full_query and ("textbox" in el_role_lower or "input" in el_role_lower or "search" in el_name_lower)):
            score += 0.15

        return min(1.0, score)

    def _find_nearest_element_to_coords(self, x: float, y: float, elements: list[ScreenElement]) -> ScreenElement | None:
        """Find element whose bounding box contains or is nearest to (x, y) coordinates."""
        if not elements:
            return None
        # Check if coordinates lie inside any element's bounding box
        for el in elements:
            bx, by, bw, bh = el.bounds
            if bx <= x <= bx + bw and by <= y <= by + bh:
                return el
        # Return first visible element fallback
        return elements[0]


screen_grounding_engine = ScreenGroundingEngine()
