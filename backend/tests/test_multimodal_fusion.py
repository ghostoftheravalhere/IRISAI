"""Unit tests for Multimodal Gaze + Voice Fusion Engine and Deictic Spatial Resolution."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from backend.brain.fusion import MultimodalFusionEngine, PerceptionEvent
from backend.brain.multimodal_fusion import (
    DeicticSpatialFusionRule,
    GazeGroundedSpatialResolver,
    GroundedSpatialTarget,
)
from backend.eye_tracking.calibration import EyeCenter
from backend.eye_tracking.gaze_service import EyeGazeService, GazeEstimate
from backend.perception.ui_automation_engine import AccessibilityElement, UIAutomationEngine


def make_gaze(x: float = 0.5, y: float = 0.5, confidence: float = 0.9, age_offset: float = 0.0) -> GazeEstimate:
    return GazeEstimate(
        eye_center=EyeCenter(x=0.5, y=0.5),
        raw_x=x,
        raw_y=y,
        x=x,
        y=y,
        confidence=confidence,
        captured_at=time.time() - age_offset,
    )


# Test Scenario 1: "Click this" + valid gaze -> Successful spatial click fusion
def test_click_this_valid_gaze():
    gaze_mock = MagicMock(spec=EyeGazeService)
    gaze_mock.get_latest_gaze.return_value = make_gaze(x=0.2, y=0.3, confidence=0.85)

    resolver = GazeGroundedSpatialResolver(gaze_service=gaze_mock)
    rule = DeicticSpatialFusionRule(spatial_resolver=resolver)
    engine = MultimodalFusionEngine(rules=[rule])

    evt = PerceptionEvent(source="voice", intent="CLICK", raw_text="Click this", confidence=0.9)
    res = engine.ingest_event(evt)

    assert res.unified_intent == "PRIMARY_CLICK"
    assert res.rule_applied == "DeicticSpatialFusionRule"
    assert res.params["gaze_x"] == 0.2
    assert res.params["gaze_y"] == 0.3
    assert res.combined_confidence > 0.8


# Test Scenario 2: "Click this" + low confidence -> Safe target unavailable rejection
def test_click_this_low_confidence_gaze():
    gaze_mock = MagicMock(spec=EyeGazeService)
    gaze_mock.get_latest_gaze.return_value = make_gaze(x=0.2, y=0.3, confidence=0.20)

    resolver = GazeGroundedSpatialResolver(gaze_service=gaze_mock)
    rule = DeicticSpatialFusionRule(spatial_resolver=resolver)
    engine = MultimodalFusionEngine(rules=[rule])

    evt = PerceptionEvent(source="voice", intent="CLICK", raw_text="Click this", confidence=0.9)
    res = engine.ingest_event(evt)

    assert res.unified_intent == "TARGET_UNAVAILABLE"
    assert "TargetUnavailable" in res.rule_applied
    assert res.target is None


# Test Scenario 3: "Open that" + valid target -> Resolved spatial open request
def test_open_that_valid_target():
    gaze_mock = MagicMock(spec=EyeGazeService)
    gaze_mock.get_latest_gaze.return_value = make_gaze(x=0.7, y=0.1, confidence=0.9)

    resolver = GazeGroundedSpatialResolver(gaze_service=gaze_mock)
    rule = DeicticSpatialFusionRule(spatial_resolver=resolver)
    engine = MultimodalFusionEngine(rules=[rule])

    evt = PerceptionEvent(source="voice", intent="OPEN", raw_text="Open that", confidence=0.95)
    res = engine.ingest_event(evt)

    assert res.unified_intent == "OPEN_APPLICATION"
    assert res.params["gaze_x"] == 0.7
    assert res.params["gaze_y"] == 0.1


# Test Scenario 4: "Type hello here" + valid target -> Resolved spatial input action
def test_type_hello_here_valid_target():
    gaze_mock = MagicMock(spec=EyeGazeService)
    gaze_mock.get_latest_gaze.return_value = make_gaze(x=0.4, y=0.6, confidence=0.88)

    resolver = GazeGroundedSpatialResolver(gaze_service=gaze_mock)
    rule = DeicticSpatialFusionRule(spatial_resolver=resolver)
    engine = MultimodalFusionEngine(rules=[rule])

    evt = PerceptionEvent(source="voice", intent="TYPE", raw_text="Type hello here", params={"text": "hello"}, confidence=0.9)
    res = engine.ingest_event(evt)

    assert res.unified_intent == "TYPE_TEXT"
    assert res.params["text"] == "hello"
    assert res.params["gaze_x"] == 0.4
    assert res.params["gaze_y"] == 0.6


# Test Scenario 5: Missing gaze -> Safe target unavailable rejection
def test_missing_gaze_rejection():
    gaze_mock = MagicMock(spec=EyeGazeService)
    gaze_mock.get_latest_gaze.return_value = None

    resolver = GazeGroundedSpatialResolver(gaze_service=gaze_mock)
    rule = DeicticSpatialFusionRule(spatial_resolver=resolver)
    engine = MultimodalFusionEngine(rules=[rule])

    evt = PerceptionEvent(source="voice", intent="CLICK", raw_text="Click this", confidence=0.9)
    res = engine.ingest_event(evt)

    assert res.unified_intent == "TARGET_UNAVAILABLE"


# Test Scenario 6: Stale gaze (> 500ms) -> Safe stale gaze rejection
def test_stale_gaze_rejection():
    gaze_mock = MagicMock(spec=EyeGazeService)
    gaze_mock.get_latest_gaze.return_value = make_gaze(x=0.5, y=0.5, confidence=0.9, age_offset=1.5)

    resolver = GazeGroundedSpatialResolver(gaze_service=gaze_mock)
    rule = DeicticSpatialFusionRule(spatial_resolver=resolver)
    engine = MultimodalFusionEngine(rules=[rule])

    evt = PerceptionEvent(source="voice", intent="CLICK", raw_text="Click this", confidence=0.9)
    res = engine.ingest_event(evt)

    assert res.unified_intent == "TARGET_UNAVAILABLE"


# Test Scenario 7: Target resolution failure -> Safe coordinate fallback
def test_target_resolution_fallback():
    gaze_mock = MagicMock(spec=EyeGazeService)
    gaze_mock.get_latest_gaze.return_value = make_gaze(x=0.3, y=0.3, confidence=0.8)

    uia_mock = MagicMock(spec=UIAutomationEngine)
    uia_mock.find_all.side_effect = Exception("UIA tree failed")

    resolver = GazeGroundedSpatialResolver(gaze_service=gaze_mock, uia_engine=uia_mock)
    rule = DeicticSpatialFusionRule(spatial_resolver=resolver)
    engine = MultimodalFusionEngine(rules=[rule])

    evt = PerceptionEvent(source="voice", intent="CLICK", raw_text="Click this", confidence=0.9)
    res = engine.ingest_event(evt)

    assert res.unified_intent == "PRIMARY_CLICK"
    assert res.params["gaze_x"] == 0.3


# Test Scenario 8: Unrelated voice command ("Open Chrome") -> Unchanged voice-only rule
def test_unrelated_voice_command():
    engine = MultimodalFusionEngine()
    evt = PerceptionEvent(source="voice", intent="OPEN_APPLICATION", raw_text="Open Chrome", target="Chrome", confidence=0.95)
    res = engine.ingest_event(evt)

    assert res.unified_intent == "OPEN_APPLICATION"
    assert res.target == "Chrome"
    assert res.rule_applied == "VoiceOnlyFusionRule"


# Test Scenario 9: Normal existing voice command remains unchanged
def test_normal_existing_voice_command():
    engine = MultimodalFusionEngine()
    evt = PerceptionEvent(source="voice", intent="SEARCH", raw_text="Search ChatGPT", target="ChatGPT", confidence=0.92)
    res = engine.ingest_event(evt)

    assert res.unified_intent == "SEARCH"
    assert res.rule_applied == "VoiceOnlyFusionRule"


# Test Scenario 10: Existing eye-only action remains unchanged
def test_existing_eye_only_action():
    engine = MultimodalFusionEngine()
    evt = PerceptionEvent(source="eye_tracking", intent="BLINK_CLICK", target="Button_0", confidence=0.88)
    res = engine.ingest_event(evt)

    assert res.unified_intent == "BLINK_CLICK"
    assert res.sources == ["eye_tracking"]
