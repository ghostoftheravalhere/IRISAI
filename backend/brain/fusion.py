"""Multimodal Fusion Engine for perception stream correlation and unified intent generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
import time
from typing import Any, Protocol, Sequence
import uuid

from backend.brain.fusion_events import FusionAttemptedEvent, FusionCompletedEvent
from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PerceptionEvent:
    """Generic multi-sensor perception event model."""

    source: str
    intent: str
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
    target: str | None = None
    raw_text: str = ""
    query: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True)
class FusionRequest:
    """Request bundling perception events for multimodal correlation."""

    events: list[PerceptionEvent]
    primary_source: str = "voice"


@dataclass
class FusionResult:
    """Consolidated outcome of multimodal perception fusion."""

    unified_intent: str
    combined_confidence: float
    target: str | None = None
    sources: list[str] = field(default_factory=list)
    rule_applied: str = ""
    raw_text: str = ""
    query: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


class FusionRule(Protocol):
    """Protocol for modular multimodal fusion rules."""

    def fuse(self, events: list[PerceptionEvent]) -> FusionResult | None:
        """Attempt to fuse perception events into a unified result; return None if rule does not match."""
        ...


@dataclass(frozen=True)
class VoiceOnlyFusionRule:
    """Pass-through fusion rule for single-modality voice perception."""

    def fuse(self, events: list[PerceptionEvent]) -> FusionResult | None:
        """Fuse voice perception events when no conflicting modalities are present."""
        if not events:
            return None

        voice_events = [e for e in events if e.source == "voice"]
        if len(events) == len(voice_events) and len(voice_events) > 0:
            latest = voice_events[-1]
            return FusionResult(
                unified_intent=latest.intent,
                combined_confidence=latest.confidence,
                target=latest.target,
                sources=["voice"],
                rule_applied="VoiceOnlyFusionRule",
                raw_text=latest.raw_text,
                query=latest.query,
                params=latest.params,
            )
        return None


@dataclass(frozen=True)
class GazeVoiceFusionRule:
    """Correlates eye-gaze target with voice action verb within a temporal window."""

    def fuse(self, events: list[PerceptionEvent]) -> FusionResult | None:
        """Fuse gaze target and voice verb into a unified application command."""
        gaze_events = [e for e in events if e.source in ("gaze", "eye_tracking") and e.target]
        voice_events = [e for e in events if e.source == "voice"]

        if gaze_events and voice_events:
            gaze = gaze_events[-1]
            voice = voice_events[-1]

            # If voice verb is open/close or target matches gaze target
            combined_conf = min(1.0, (gaze.confidence + voice.confidence) / 2.0 + 0.1)
            target_app = gaze.target or voice.target

            return FusionResult(
                unified_intent=voice.intent,
                combined_confidence=combined_conf,
                target=target_app,
                sources=["gaze", "voice"],
                rule_applied="GazeVoiceFusionRule",
                raw_text=voice.raw_text,
                query=voice.query,
                params=voice.params,
            )
        return None


@dataclass(frozen=True)
class ConflictResolutionRule:
    """Resolves competing perception events based on confidence scoring and source priority."""

    def fuse(self, events: list[PerceptionEvent]) -> FusionResult | None:
        """Select highest-confidence event giving preference to voice on ties."""
        if not events:
            return None

        # Sort by confidence descending, then source priority ("voice" preferred)
        sorted_events = sorted(
            events,
            key=lambda e: (e.confidence, 1 if e.source == "voice" else 0),
            reverse=True,
        )
        winner = sorted_events[0]
        return FusionResult(
            unified_intent=winner.intent,
            combined_confidence=winner.confidence,
            target=winner.target,
            sources=list({e.source for e in events}),
            rule_applied="ConflictResolutionRule",
            raw_text=winner.raw_text,
            query=winner.query,
            params=winner.params,
        )


class MultimodalFusionEngine:
    """Correlates perception streams within a sliding temporal window to generate fused commands."""

    def __init__(
        self,
        window_ms: float = 500.0,
        min_confidence: float = 0.5,
        rules: Sequence[FusionRule] | None = None,
        event_bus: EventBus | None = None,
        enabled: bool = True,
    ) -> None:
        self._window_ms = window_ms
        self._min_confidence = min_confidence
        if rules is not None:
            self._rules = list(rules)
        else:
            from backend.brain.multimodal_fusion import DeicticSpatialFusionRule
            self._rules = [
                DeicticSpatialFusionRule(),
                VoiceOnlyFusionRule(),
                GazeVoiceFusionRule(),
                ConflictResolutionRule(),
            ]
        self._event_bus = event_bus
        self._enabled = enabled
        self._events_buffer: list[PerceptionEvent] = []
        self._lock = RLock()

    @property
    def enabled(self) -> bool:
        """Return whether fusion engine is active."""
        return self._enabled

    def ingest_event(self, event: PerceptionEvent) -> FusionResult:
        """Ingest a perception event and return the fused result."""
        with self._lock:
            now = time.time()
            window_sec = self._window_ms / 1000.0

            # Purge expired events outside temporal correlation window
            self._events_buffer = [e for e in self._events_buffer if (now - e.timestamp) <= window_sec]
            self._events_buffer.append(event)
            active_events = list(self._events_buffer)

        if self._event_bus:
            self._event_bus.publish(
                FusionAttemptedEvent(
                    event_count=len(active_events),
                    sources=list({e.source for e in active_events}),
                    window_ms=self._window_ms,
                )
            )

        if not self._enabled:
            # Fallback pass-through when disabled
            return FusionResult(
                unified_intent=event.intent,
                combined_confidence=event.confidence,
                target=event.target,
                sources=[event.source],
                rule_applied="PassThroughDisabled",
                raw_text=event.raw_text,
                query=event.query,
                params=event.params,
            )

        # Evaluate rules in priority sequence
        for rule in self._rules:
            result = rule.fuse(active_events)
            if result is not None and result.combined_confidence >= self._min_confidence:
                if self._event_bus:
                    self._event_bus.publish(
                        FusionCompletedEvent(
                            unified_intent=result.unified_intent,
                            combined_confidence=result.combined_confidence,
                            selected_rule=result.rule_applied,
                            target=result.target,
                        )
                    )
                return result

        # Default fallback to latest ingested event
        fallback = FusionResult(
            unified_intent=event.intent,
            combined_confidence=event.confidence,
            target=event.target,
            sources=[event.source],
            rule_applied="DefaultFallback",
            raw_text=event.raw_text,
            query=event.query,
            params=event.params,
        )
        return fallback
