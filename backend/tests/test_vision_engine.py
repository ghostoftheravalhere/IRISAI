"""Unit tests for Vision Intelligence Subsystem."""

from __future__ import annotations

from backend.core.events.bus import EventBus
from backend.perception.ocr_service import OCREngine
from backend.perception.ui_element_detector import UIElementDetector
from backend.perception.vision_engine import VisionEngine, WindowRect
from backend.perception.vision_events import (
    OCRCompletedEvent,
    ScreenCapturedEvent,
    VisualContextUpdatedEvent,
)
from backend.perception.vision_privacy import VisionPrivacyFilter
from backend.perception.visual_context import VisualContextGenerator


def test_vision_privacy_filter():
    privacy = VisionPrivacyFilter(blacklisted_apps=["1password", "bitwarden"])
    assert privacy.is_window_allowed("Google Chrome") is True
    assert privacy.is_window_allowed("1Password - Vault") is False
    assert privacy.is_window_allowed("Bitwarden - Passwords") is False

    redacted = privacy.sanitize_ocr_text("My card is 4111 2222 3333 4444 and password: secret123")
    assert "[REDACTED CARD]" in redacted
    assert "[REDACTED SECRET]" in redacted


def test_ocr_service_and_ui_element_detector():
    ocr_engine = OCREngine()
    res = ocr_engine.process_image(None, offset_x=100, offset_y=100)
    assert len(res.boxes) > 0
    assert "Settings" in res.full_text

    detector = UIElementDetector()
    match = detector.find_element("Camera", res)
    assert match is not None
    assert match.label == "Camera"
    assert match.center_x > 0
    assert match.center_y > 0


def test_vision_engine_pipeline():
    event_bus = EventBus()
    events_received = []

    def _on_event(event):
        events_received.append(event)

    event_bus.subscribe(ScreenCapturedEvent, _on_event)
    event_bus.subscribe(OCRCompletedEvent, _on_event)
    event_bus.subscribe(VisualContextUpdatedEvent, _on_event)

    engine = VisionEngine(event_bus=event_bus)
    context = engine.capture_and_process("Settings")

    assert context.app_title == "Settings"
    assert context.element_count > 0
    assert len(events_received) == 3


def test_vision_privacy_blocked_capture():
    engine = VisionEngine()
    context = engine.capture_and_process("1Password - Vault")

    assert context.app_title == "1Password - Vault"
    assert context.visible_text == "[PRIVACY BLOCKED]"
    assert context.element_count == 0
