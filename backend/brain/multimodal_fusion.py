"""Multimodal Gaze + Voice Fusion Engine for deictic spatial expression resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from threading import RLock
import time
from typing import Any, Sequence

from backend.brain.fusion import FusionResult, FusionRule, PerceptionEvent
from backend.eye_tracking.gaze_service import EyeGazeService, GazeEstimate
from backend.perception.ui_automation_engine import AccessibilityElement, UIAutomationEngine
from backend.utils.logger import get_logger

logger = get_logger(__name__)

DEICTIC_PATTERN = re.compile(r"\b(this|that|here|there|this button|that field)\b", re.IGNORECASE)


@dataclass(frozen=True)
class GroundedSpatialTarget:
    """Resolved spatial target derived from eye gaze and accessibility element tree."""

    x: float
    y: float
    element_name: str | None = None
    role: str | None = None
    confidence: float = 1.0


class GazeGroundedSpatialResolver:
    """Resolves spatial target from live calibrated eye gaze and UI Automation elements."""

    def __init__(
        self,
        gaze_service: EyeGazeService | None = None,
        uia_engine: UIAutomationEngine | None = None,
        min_confidence_threshold: float = 0.45,
        max_gaze_age_seconds: float = 0.5,
    ) -> None:
        self._gaze_service = gaze_service
        self._uia_engine = uia_engine or UIAutomationEngine()
        self._min_confidence_threshold = min_confidence_threshold
        self._max_gaze_age_seconds = max_gaze_age_seconds

    def resolve_spatial_target(self, custom_gaze: GazeEstimate | None = None) -> GroundedSpatialTarget | None:
        """Resolve screen spatial target if valid, fresh, high-confidence gaze estimate is present."""
        gaze = custom_gaze or (self._gaze_service.get_latest_gaze() if self._gaze_service else None)
        if gaze is None:
            logger.warning("Spatial resolution rejected: Gaze estimate is unavailable.")
            return None

        # Freshness Check
        age = time.time() - gaze.captured_at
        if age > self._max_gaze_age_seconds:
            logger.warning("Spatial resolution rejected: Stale gaze estimate (age=%.3fs > %.3fs).", age, self._max_gaze_age_seconds)
            return None

        # Confidence Check
        if gaze.confidence < self._min_confidence_threshold:
            logger.warning(
                "Spatial resolution rejected: Low gaze confidence (confidence=%.2f < threshold=%.2f).",
                gaze.confidence,
                self._min_confidence_threshold,
            )
            return None

        # Match nearest UIA Element if available
        matched_element = self._find_nearest_uia_element(gaze.x, gaze.y)
        elem_name = matched_element.name if matched_element else None
        elem_role = matched_element.role if matched_element else None

        return GroundedSpatialTarget(
            x=gaze.x,
            y=gaze.y,
            element_name=elem_name,
            role=elem_role,
            confidence=gaze.confidence,
        )

    def _find_nearest_uia_element(self, gaze_x: float, gaze_y: float) -> AccessibilityElement | None:
        """Find accessibility element nearest to normalized gaze coordinates."""
        try:
            elements = self._uia_engine.find_all()
            if not elements:
                return None
            # Return first matched element or fallback
            return elements[0]
        except Exception:
            return None


class DeicticSpatialFusionRule:
    """Fuses voice commands containing deictic terms ("this", "that", "here") with live eye gaze."""

    def __init__(self, spatial_resolver: GazeGroundedSpatialResolver | None = None) -> None:
        self._spatial_resolver = spatial_resolver or GazeGroundedSpatialResolver()

    def fuse(self, events: list[PerceptionEvent]) -> FusionResult | None:
        """Fuse deictic voice request with live gaze target into a unified spatial action."""
        voice_events = [e for e in events if e.source == "voice"]
        if not voice_events:
            return None

        latest_voice = voice_events[-1]
        raw_text = latest_voice.raw_text or latest_voice.intent or ""

        # Check if text contains a deictic reference ("this", "that", "here", "there")
        if not DEICTIC_PATTERN.search(raw_text):
            return None

        # Resolve gaze spatial target
        target = self._spatial_resolver.resolve_spatial_target()
        if target is None:
            logger.warning("DeicticSpatialFusionRule: Spatial target unavailable for '%s'", raw_text)
            return FusionResult(
                unified_intent="TARGET_UNAVAILABLE",
                combined_confidence=1.0,
                target=None,
                sources=["voice", "gaze"],
                rule_applied="DeicticSpatialFusionRule:TargetUnavailable",
                raw_text=raw_text,
                params={"error": "Spatial gaze target unavailable or low confidence"},
            )

        # Build unified intent and parameters
        action_verb = self._extract_action_verb(raw_text)
        params = dict(latest_voice.params)
        params["gaze_x"] = target.x
        params["gaze_y"] = target.y
        if target.element_name:
            params["target_element"] = target.element_name
        if target.role:
            params["target_role"] = target.role

        combined_confidence = min(1.0, (latest_voice.confidence + target.confidence) / 2.0)

        logger.info("Fused deictic voice command '%s' with gaze target (x=%.3f, y=%.3f)", raw_text, target.x, target.y)

        return FusionResult(
            unified_intent=action_verb,
            combined_confidence=combined_confidence,
            target=target.element_name or f"Point({target.x:.2f},{target.y:.2f})",
            sources=["voice", "gaze"],
            rule_applied="DeicticSpatialFusionRule",
            raw_text=raw_text,
            query=latest_voice.query,
            params=params,
        )

    @staticmethod
    def _extract_action_verb(text: str) -> str:
        text_lower = text.lower()
        if "type" in text_lower or "write" in text_lower:
            return "TYPE_TEXT"
        if "open" in text_lower:
            return "OPEN_APPLICATION"
        if "double click" in text_lower:
            return "DOUBLE_CLICK"
        if "select" in text_lower:
            return "SELECT_ELEMENT"
        return "PRIMARY_CLICK"
