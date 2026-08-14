"""Unit tests for Sprint 5 EventBus and Voice Telemetry infrastructure."""

from dataclasses import dataclass

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.core.events.bus import DomainEvent, EventBus
from backend.voice.telemetry import (
    AudioCapturedEvent,
    AutomationExecutedEvent,
    IntentParsedEvent,
    TranscriptionCompletedEvent,
    VoiceTelemetryService,
)


@dataclass
class CustomTestEvent(DomainEvent):
    value: str = ""


def test_event_bus_subscribe_publish_unsubscribe():
    bus = EventBus()
    received = []

    def handler(event: CustomTestEvent) -> None:
        received.append(event.value)

    bus.subscribe(CustomTestEvent, handler)
    evt1 = CustomTestEvent(value="first")
    bus.publish(evt1)
    assert received == ["first"]

    bus.unsubscribe(CustomTestEvent, handler)
    evt2 = CustomTestEvent(value="second")
    bus.publish(evt2)
    assert received == ["first"]  # Handled only once before unsubscribe


def test_event_bus_isolated_handler_exceptions():
    bus = EventBus()
    received = []

    def failing_handler(event: CustomTestEvent) -> None:
        raise RuntimeError("Handler failure")

    def successful_handler(event: CustomTestEvent) -> None:
        received.append(event.value)

    bus.subscribe(CustomTestEvent, failing_handler)
    bus.subscribe(CustomTestEvent, successful_handler)

    bus.publish(CustomTestEvent(value="test"))
    assert received == ["test"]


def test_voice_telemetry_service_aggregates_metrics():
    bus = EventBus()
    telemetry = VoiceTelemetryService(event_bus=bus, enabled=True, capacity=10)

    # Publish sequence of events for 2 utterances
    bus.publish(AudioCapturedEvent(raw_rms=0.005, raw_peak=0.05, duration_seconds=1.2, is_ptt=True))
    bus.publish(TranscriptionCompletedEvent(raw_transcript="open chrome", whisper_latency_ms=120.0))
    bus.publish(IntentParsedEvent(raw_transcript="open chrome", normalized_transcript="open chrome", intent="OPEN_CHROME"))
    bus.publish(AutomationExecutedEvent(intent="OPEN_CHROME", action="OPEN_CHROME", success=True, execution_status="Chrome opened"))

    bus.publish(AudioCapturedEvent(raw_rms=0.008, raw_peak=0.08, duration_seconds=1.0, is_ptt=False))
    bus.publish(TranscriptionCompletedEvent(raw_transcript="copy", whisper_latency_ms=80.0))
    bus.publish(IntentParsedEvent(raw_transcript="copy", normalized_transcript="copy", intent="COPY"))
    bus.publish(AutomationExecutedEvent(intent="COPY", action="COPY", success=True, execution_status="Copied"))

    summary = telemetry.get_summary()

    assert summary["enabled"] is True
    assert summary["totalUtterances"] == 2
    assert summary["avgWhisperLatencyMs"] == 100.0  # (120 + 80) / 2
    assert summary["successfulIntents"] == 2
    assert summary["latestTrace"]["intent"] == "COPY"


def test_telemetry_buffer_capacity_eviction():
    bus = EventBus()
    telemetry = VoiceTelemetryService(event_bus=bus, enabled=True, capacity=3)

    for i in range(5):
        bus.publish(AudioCapturedEvent(raw_rms=0.001 * i, raw_peak=0.01 * i, duration_seconds=1.0))

    events = telemetry.get_events()
    assert len(events) == 3  # Capacity capped at 3 entries
    assert events[-1]["rawPeak"] == 0.04


def test_voice_telemetry_api_route():
    app = create_app()
    client = TestClient(app)

    response = client.get("/voice/telemetry")
    assert response.status_code == 200
    data = response.json()

    assert "enabled" in data
    assert "totalUtterances" in data
    assert "avgWhisperLatencyMs" in data
    assert "successfulIntents" in data
    assert "bufferCapacity" in data
