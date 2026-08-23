"""Unit tests for Sprint 8 Multimodal Fusion Engine and Rules."""

from __future__ import annotations

from dataclasses import dataclass
import time

from backend.automation.controller import DesktopController
from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.context_manager import ContextManager
from backend.brain.fusion import (
    ConflictResolutionRule,
    FusionResult,
    GazeVoiceFusionRule,
    MultimodalFusionEngine,
    PerceptionEvent,
    VoiceOnlyFusionRule,
)
from backend.brain.fusion_events import FusionAttemptedEvent, FusionCompletedEvent
from backend.brain.intent_manager import IntentManager
from backend.brain.orchestrator import BrainOrchestrator
from backend.config.settings import settings
from backend.core.di.container import build_container
from backend.core.events.bus import EventBus
from backend.eye_tracking.action_engine import ActionEngine, ActionType
from backend.voice.command_parser import IntentParserService
from backend.voice.pipeline import VoiceCommandPipeline


class _FakeDesktop(DesktopController):
    def open_application(self, app_name: str) -> bool:
        return True

    def hotkey(self, *keys: str) -> bool:
        return True


class _FakeActionEngine(ActionEngine):
    def get_latest_state(self):
        @dataclass
        class State:
            action = ActionType.NO_ACTION
            cursorPaused = False
        return State()


def test_voice_only_fusion_rule():
    rule = VoiceOnlyFusionRule()
    event = PerceptionEvent(source="voice", intent="OPEN_CHROME", confidence=0.9, raw_text="open chrome")

    result = rule.fuse([event])
    assert result is not None
    assert result.unified_intent == "OPEN_CHROME"
    assert result.sources == ["voice"]
    assert result.rule_applied == "VoiceOnlyFusionRule"


def test_gaze_voice_fusion_rule():
    rule = GazeVoiceFusionRule()
    gaze_evt = PerceptionEvent(source="gaze", intent="GAZE_FOCUS", confidence=0.8, target="notepad")
    voice_evt = PerceptionEvent(source="voice", intent="OPEN_APPLICATION", confidence=0.9, raw_text="open")

    result = rule.fuse([gaze_evt, voice_evt])
    assert result is not None
    assert result.unified_intent == "OPEN_APPLICATION"
    assert result.target == "notepad"
    assert "gaze" in result.sources
    assert "voice" in result.sources
    assert result.rule_applied == "GazeVoiceFusionRule"


def test_conflict_resolution_rule():
    rule = ConflictResolutionRule()
    e1 = PerceptionEvent(source="gaze", intent="SCROLL_DOWN", confidence=0.6)
    e2 = PerceptionEvent(source="voice", intent="OPEN_CHROME", confidence=0.8, raw_text="open chrome")

    result = rule.fuse([e1, e2])
    assert result is not None
    assert result.unified_intent == "OPEN_CHROME"
    assert result.rule_applied == "ConflictResolutionRule"


def test_fusion_engine_temporal_window_eviction():
    engine = MultimodalFusionEngine(window_ms=100.0, enabled=True)

    e_old = PerceptionEvent(source="gaze", intent="GAZE_FOCUS", confidence=0.9, target="chrome", timestamp=time.time() - 0.2)
    engine.ingest_event(e_old)

    e_new = PerceptionEvent(source="voice", intent="OPEN_APPLICATION", confidence=0.9, raw_text="open")
    res = engine.ingest_event(e_new)

    # e_old was evicted, so VoiceOnlyFusionRule applies to e_new
    assert res.rule_applied == "VoiceOnlyFusionRule"
    assert res.sources == ["voice"]


def test_fusion_engine_event_bus_emission():
    event_bus = EventBus()
    events_captured = []
    event_bus.subscribe(FusionAttemptedEvent, lambda e: events_captured.append(e))
    event_bus.subscribe(FusionCompletedEvent, lambda e: events_captured.append(e))

    engine = MultimodalFusionEngine(window_ms=500.0, event_bus=event_bus, enabled=True)
    pevent = PerceptionEvent(source="voice", intent="OPEN_CHROME", raw_text="open chrome")

    result = engine.ingest_event(pevent)
    assert result.unified_intent == "OPEN_CHROME"
    assert len(events_captured) == 2
    assert isinstance(events_captured[0], FusionAttemptedEvent)
    assert isinstance(events_captured[1], FusionCompletedEvent)


def test_voice_pipeline_routes_through_fusion_engine_and_orchestrator():
    orchestrator = BrainOrchestrator(
        intent_manager=IntentManager(),
        context_manager=ContextManager(),
        automation_dispatcher=AutomationDispatcher(_FakeDesktop()),
        enabled=True,
    )
    fusion_engine = MultimodalFusionEngine(window_ms=500.0, enabled=True)

    pipeline = VoiceCommandPipeline(
        intent_parser=IntentParserService(),
        action_engine=_FakeActionEngine(),
        automation_dispatcher=AutomationDispatcher(_FakeDesktop()),
        orchestrator=orchestrator,
        fusion_engine=fusion_engine,
    )

    result = pipeline.execute("open chrome")
    assert result.success is True
    assert result.intent == "OPEN_CHROME"


def test_di_container_wires_fusion_engine():
    container = build_container(settings)
    assert container.fusion_engine is not None
    assert container.fusion_engine.enabled is True
