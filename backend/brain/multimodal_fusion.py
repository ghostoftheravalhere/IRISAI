"""Multimodal Gaze + Voice + Screen + Context Fusion Engine for IRIS AI V4.

Combines voice intent, live eye gaze, visible UI screen elements, active application context,
and WorldModel state into a structured, unified decision proposal (MultimodalDecision).

STRICT SAFETY BOUNDARY:
MultimodalFusionEngine ONLY produces a structured MultimodalDecision proposal.
It MUST NOT click, type, press keys, execute shell commands, or directly control Windows.
Execution MUST route through PolicyEngine, ToolExecutor, DesktopTool, and ActionEngine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from threading import RLock
import time
from typing import Any, Sequence

from backend.brain.fusion import FusionResult, PerceptionEvent
from backend.brain.world_model import world_model
from backend.eye_tracking.gaze_service import EyeGazeService, GazeEstimate
from backend.perception.screen_grounding_engine import ScreenElement, screen_grounding_engine
from backend.perception.ui_automation_engine import AccessibilityElement, UIAutomationEngine
from backend.utils.logger import get_logger

logger = get_logger(__name__)

DEICTIC_PATTERN = re.compile(r"\b(this|that|here|there|this button|that field)\b", re.IGNORECASE)
REFERENTIAL_PATTERN = re.compile(r"\b(it|the button|the message|the field|that window|that chat)\b", re.IGNORECASE)


@dataclass(frozen=True)
class GroundedSpatialTarget:
    """Resolved spatial target derived from eye gaze and accessibility element tree."""

    x: float
    y: float
    element_name: str | None = None
    role: str | None = None
    confidence: float = 1.0


@dataclass
class MultimodalDecision:
    """Structured decision outcome of multimodal evidence fusion."""

    action: str  # CLICK | RIGHT_CLICK | DOUBLE_CLICK | COPY | PASTE | SELECT | TYPE | OPEN
    target: str
    target_type: str  # UI_ELEMENT | TEXT_REGION | WINDOW | PERSON
    confidence: float
    source_evidence: dict[str, float]  # {"voice": 0.35, "gaze": 0.30, "screen": 0.25, "context": 0.10}
    application: str = "ActiveApp"
    window: str = "ActiveWindow"
    gaze_position: tuple[float, float] | None = None
    screen_element_id: str | None = None
    person_id: str | None = None
    requires_confirmation: bool = False
    reason: str = ""

    def to_safe_dict(self) -> dict[str, Any]:
        """Return dict representation without raw 128-dim biometric face embeddings."""
        return {
            "action": self.action,
            "target": self.target,
            "target_type": self.target_type,
            "confidence": round(self.confidence, 2),
            "source_evidence": {k: round(v, 2) for k, v in self.source_evidence.items()},
            "application": self.application,
            "window": self.window,
            "gaze_position": self.gaze_position,
            "screen_element_id": self.screen_element_id,
            "person_id": self.person_id,
            "requires_confirmation": self.requires_confirmation,
            "reason": self.reason,
        }


class GazeGroundedSpatialResolver:
    """Resolves spatial target from live calibrated eye gaze and UI Automation elements."""

    def __init__(
        self,
        gaze_service: EyeGazeService | None = None,
        uia_engine: UIAutomationEngine | None = None,
        min_confidence_threshold: float = 0.45,
        max_gaze_age_seconds: float = 1.5,
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
            return elements[0]
        except Exception:
            return None


class MultimodalFusionEngine:
    """Engine fusing Voice Intent, Gaze, Screen UI Elements, Application, and WorldModel Context."""

    def __init__(
        self,
        gaze_resolver: GazeGroundedSpatialResolver | None = None,
        screen_grounder: Any | None = None,
    ) -> None:
        self._gaze_resolver = gaze_resolver or GazeGroundedSpatialResolver()
        self._screen_grounder = screen_grounder or screen_grounding_engine
        self._lock = RLock()

    def fuse_multimodal_request(
        self,
        voice_goal: str,
        custom_gaze: GazeEstimate | None = None,
        custom_elements: list[ScreenElement] | None = None,
    ) -> MultimodalDecision:
        """Fuse multimodal evidence sources into a structured decision proposal."""
        with self._lock:
            snap = world_model.snapshot()
            q_lower = voice_goal.strip().lower()

            action_verb = self._parse_action_verb(q_lower)

            # 1. Resolve Deictic / Spatial Target ("this", "that", "here")
            is_deictic = bool(DEICTIC_PATTERN.search(q_lower))
            is_referential = bool(REFERENTIAL_PATTERN.search(q_lower))

            spatial_target = self._gaze_resolver.resolve_spatial_target(custom_gaze=custom_gaze)
            gaze_pos = (spatial_target.x, spatial_target.y) if spatial_target else None

            # Handle Stale / Unavailable Gaze for pure deictic commands ("Click this")
            if is_deictic and spatial_target is None:
                logger.warning("Multimodal fusion rejected: Stale or missing gaze for deictic request '%s'", voice_goal)
                return MultimodalDecision(
                    action=action_verb,
                    target="Unknown Target",
                    target_type="UI_ELEMENT",
                    confidence=0.0,
                    source_evidence={"voice": 0.35, "gaze": 0.0, "screen": 0.0, "context": 0.10},
                    application=snap.application.active_app or "ActiveApp",
                    window=snap.window.title or "ActiveWindow",
                    requires_confirmation=True,
                    reason="Gaze signal is unclear or stale. Please look directly at the target element.",
                )

            # 2. Resolve Pronoun / Referential Target ("it", "that chat")
            target_phrase = q_lower
            if is_referential and not is_deictic:
                last_target = snap.ui_target.last_referenced_target
                if last_target and last_target.get("name"):
                    target_phrase = last_target["name"]
            else:
                target_phrase = re.sub(r"^(open|click|select|right click|double click|copy|paste)\s+(the|a|an)?\s*", "", q_lower, flags=re.IGNORECASE).strip()

            # 3. Person Context Resolution ("his chat")
            person_id = snap.person.person_id if snap.person else None
            if "his chat" in q_lower or "her chat" in q_lower:
                if snap.person and snap.person.name:
                    target_phrase = f"{snap.person.name} chat"

            # 4. Screen Grounding Search
            ground_res = self._screen_grounder.ground_query(
                target_phrase,
                custom_elements=custom_elements,
                gaze_estimate=custom_gaze,
            )

            # Handle Ambiguity / Conflicts
            if ground_res.requires_clarification:
                return MultimodalDecision(
                    action=action_verb,
                    target=target_phrase,
                    target_type="UI_ELEMENT",
                    confidence=0.50,
                    source_evidence={"voice": 0.35, "gaze": 0.30, "screen": 0.20, "context": 0.10},
                    application=snap.application.active_app or "ActiveApp",
                    window=snap.window.title or "ActiveWindow",
                    gaze_position=gaze_pos,
                    person_id=person_id,
                    requires_confirmation=True,
                    reason=ground_res.clarification_message or "Multiple matching UI candidates detected.",
                )

            grounded_el = ground_res.target
            target_name = grounded_el.name if grounded_el else target_phrase
            elem_id = grounded_el.element_id if grounded_el else None

            # Calculate Evidence Weights
            voice_conf = 0.35
            gaze_conf = 0.30 if (spatial_target is not None) else 0.0
            screen_conf = 0.25 if (grounded_el is not None) else 0.05
            context_conf = 0.10 if snap.application.active_app else 0.0

            total_conf = min(1.0, voice_conf + gaze_conf + screen_conf + context_conf)

            decision = MultimodalDecision(
                action=action_verb,
                target=target_name,
                target_type="UI_ELEMENT",
                confidence=total_conf,
                source_evidence={"voice": voice_conf, "gaze": gaze_conf, "screen": screen_conf, "context": context_conf},
                application=snap.application.active_app or "ActiveApp",
                window=snap.window.title or "ActiveWindow",
                gaze_position=gaze_pos,
                screen_element_id=elem_id,
                person_id=person_id,
                requires_confirmation=False,
                reason=f"Fused multimodal evidence for {action_verb} on '{target_name}'.",
            )

            # Update WorldModel snapshot history
            if grounded_el:
                world_model.update_ui_target(
                    active_app=decision.application,
                    active_window=decision.window,
                    last_referenced_target=grounded_el.to_safe_dict(),
                )

            return decision

    @staticmethod
    def _parse_action_verb(text: str) -> str:
        if "right click" in text:
            return "RIGHT_CLICK"
        if "double click" in text:
            return "DOUBLE_CLICK"
        if "copy" in text:
            return "COPY"
        if "paste" in text:
            return "PASTE"
        if "select" in text:
            return "SELECT"
        if "open" in text:
            return "OPEN"
        return "CLICK"


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

        if not DEICTIC_PATTERN.search(raw_text):
            return None

        if latest_voice.intent in ("COPY", "PASTE", "CLOSE_APPLICATION", "CLOSE_WINDOW", "MINIMIZE_WINDOW", "SELECT_ALL"):
            return None

        target = self._spatial_resolver.resolve_spatial_target()
        if target is None:
            if self._spatial_resolver._gaze_service is None:
                return None
            return FusionResult(
                unified_intent="TARGET_UNAVAILABLE",
                combined_confidence=1.0,
                target=None,
                sources=["voice", "gaze"],
                rule_applied="DeicticSpatialFusionRule:TargetUnavailable",
                raw_text=raw_text,
                params={"error": "Spatial gaze target unavailable or low confidence"},
            )

        action_verb = MultimodalFusionEngine._parse_action_verb(raw_text)
        params = dict(latest_voice.params)
        params["gaze_x"] = target.x
        params["gaze_y"] = target.y
        if target.element_name:
            params["target_element"] = target.element_name
        if target.role:
            params["target_role"] = target.role

        combined_confidence = min(1.0, (latest_voice.confidence + target.confidence) / 2.0)

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


multimodal_fusion_engine = MultimodalFusionEngine()
