"""Voice Telemetry & Perception Performance Observability Service."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import RLock
from typing import Any

from backend.core.events.bus import DomainEvent, EventBus
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AudioCapturedEvent(DomainEvent):
    """Event emitted when a raw audio clip is captured for recognition."""

    raw_rms: float = 0.0
    raw_peak: float = 0.0
    duration_seconds: float = 0.0
    is_ptt: bool = False


@dataclass
class TranscriptionCompletedEvent(DomainEvent):
    """Event emitted when Faster-Whisper completes transcribing an audio clip."""

    raw_transcript: str = ""
    whisper_latency_ms: float = 0.0
    no_speech_prob: float = 0.0
    avg_logprob: float = 0.0


@dataclass
class IntentParsedEvent(DomainEvent):
    """Event emitted when TranscriptNormalizer and IntentParser process a transcript."""

    raw_transcript: str = ""
    normalized_transcript: str = ""
    intent: str | None = None
    rule_applied: str | None = None


@dataclass
class AutomationExecutedEvent(DomainEvent):
    """Event emitted when DesktopController executes an automated action."""

    intent: str = ""
    action: str = ""
    success: bool = True
    execution_status: str = "Idle"


class VoiceTelemetryService:
    """Collects and aggregates structured perception and execution telemetry metrics."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        enabled: bool = True,
        capacity: int = 100,
    ) -> None:
        self._enabled = enabled
        self._capacity = capacity
        self._lock = RLock()
        self._buffer: deque[dict[str, Any]] = deque(maxlen=capacity)

        self._total_utterances = 0
        self._total_whisper_latency_ms = 0.0
        self._successful_intents = 0
        self._latest_trace: dict[str, Any] | None = None

        if event_bus is not None and enabled:
            event_bus.subscribe(AudioCapturedEvent, self.on_audio_captured)
            event_bus.subscribe(TranscriptionCompletedEvent, self.on_transcription_completed)
            event_bus.subscribe(IntentParsedEvent, self.on_intent_parsed)
            event_bus.subscribe(AutomationExecutedEvent, self.on_automation_executed)

    def on_audio_captured(self, event: AudioCapturedEvent) -> None:
        """Handle AudioCapturedEvent."""
        if not self._enabled:
            return
        with self._lock:
            self._total_utterances += 1
            trace = {
                "eventId": event.event_id,
                "timestamp": event.timestamp,
                "rawRms": event.raw_rms,
                "rawPeak": event.raw_peak,
                "durationSeconds": event.duration_seconds,
                "isPtt": event.is_ptt,
            }
            self._latest_trace = trace
            self._buffer.append({"type": "AudioCaptured", **trace})

    def on_transcription_completed(self, event: TranscriptionCompletedEvent) -> None:
        """Handle TranscriptionCompletedEvent."""
        if not self._enabled:
            return
        with self._lock:
            self._total_whisper_latency_ms += event.whisper_latency_ms
            trace = {
                "rawTranscript": event.raw_transcript,
                "whisperLatencyMs": round(event.whisper_latency_ms, 2),
                "noSpeechProb": round(event.no_speech_prob, 4),
                "avgLogprob": round(event.avg_logprob, 4),
            }
            if self._latest_trace:
                self._latest_trace.update(trace)
            self._buffer.append({"type": "TranscriptionCompleted", "eventId": event.event_id, **trace})

    def on_intent_parsed(self, event: IntentParsedEvent) -> None:
        """Handle IntentParsedEvent."""
        if not self._enabled:
            return
        with self._lock:
            trace = {
                "normalizedTranscript": event.normalized_transcript,
                "intent": event.intent,
                "ruleApplied": event.rule_applied,
            }
            if self._latest_trace:
                self._latest_trace.update(trace)
            self._buffer.append({"type": "IntentParsed", "eventId": event.event_id, **trace})

    def on_automation_executed(self, event: AutomationExecutedEvent) -> None:
        """Handle AutomationExecutedEvent."""
        if not self._enabled:
            return
        with self._lock:
            if event.success:
                self._successful_intents += 1
            trace = {
                "action": event.action,
                "success": event.success,
                "executionStatus": event.execution_status,
            }
            if self._latest_trace:
                self._latest_trace.update(trace)
            self._buffer.append({"type": "AutomationExecuted", "eventId": event.event_id, **trace})

    def get_summary(self) -> dict[str, Any]:
        """Return a structured dictionary summary of collected telemetry metrics."""
        with self._lock:
            avg_latency = (
                self._total_whisper_latency_ms / self._total_utterances
                if self._total_utterances > 0
                else 0.0
            )
            return {
                "enabled": self._enabled,
                "totalUtterances": self._total_utterances,
                "avgWhisperLatencyMs": round(avg_latency, 2),
                "successfulIntents": self._successful_intents,
                "bufferCapacity": self._capacity,
                "bufferedEventsCount": len(self._buffer),
                "latestTrace": self._latest_trace,
            }

    def get_events(self) -> list[dict[str, Any]]:
        """Return all buffered event traces."""
        with self._lock:
            return list(self._buffer)
