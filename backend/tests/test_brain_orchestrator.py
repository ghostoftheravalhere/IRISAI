"""Unit tests for Sprint 6 Brain Orchestrator and Safety Validation Subsystem."""

from __future__ import annotations

from dataclasses import dataclass

from backend.automation.controller import DesktopController
from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.context_manager import ContextManager
from backend.brain.events import (
    OrchestrationBlockedEvent,
    OrchestrationCompletedEvent,
    OrchestrationRequestedEvent,
)
from backend.brain.intent_manager import IntentManager
from backend.brain.orchestrator import (
    AllowAllSafetyPolicy,
    BrainOrchestrator,
    OrchestrationRequest,
    RateLimitSafetyPolicy,
)
from backend.config.settings import settings
from backend.core.di.container import build_container
from backend.core.events.bus import EventBus
from backend.eye_tracking.action_engine import ActionEngine, ActionType
from backend.voice.command_parser import IntentParserService, VoiceIntent, VoiceIntentType
from backend.voice.pipeline import VoiceCommandPipeline


class _FakeDesktop(DesktopController):
    def open_application(self, app_name: str) -> bool:
        return True

    def copy(self) -> bool:
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


def test_brain_orchestrator_process_intent_success():
    event_bus = EventBus()
    events_captured = []

    event_bus.subscribe(OrchestrationRequestedEvent, lambda e: events_captured.append(e))
    event_bus.subscribe(OrchestrationCompletedEvent, lambda e: events_captured.append(e))

    orchestrator = BrainOrchestrator(
        intent_manager=IntentManager(),
        context_manager=ContextManager(),
        automation_dispatcher=AutomationDispatcher(_FakeDesktop()),
        event_bus=event_bus,
        safety_policies=[AllowAllSafetyPolicy()],
        enabled=True,
    )

    request = OrchestrationRequest(
        source="voice",
        intent=VoiceIntent(intent=VoiceIntentType.OPEN_CHROME, text="open chrome"),
        raw_transcript="open chrome",
    )

    response = orchestrator.process_intent(request)

    assert response.success is True
    assert response.status == "SUCCESS"
    assert response.intent == "OPEN_CHROME"
    assert len(events_captured) == 2
    assert isinstance(events_captured[0], OrchestrationRequestedEvent)
    assert isinstance(events_captured[1], OrchestrationCompletedEvent)


def test_brain_orchestrator_rate_limit_policy_blocks_repeat():
    event_bus = EventBus()
    blocked_events = []
    event_bus.subscribe(OrchestrationBlockedEvent, lambda e: blocked_events.append(e))

    orchestrator = BrainOrchestrator(
        intent_manager=IntentManager(),
        context_manager=ContextManager(),
        automation_dispatcher=AutomationDispatcher(_FakeDesktop()),
        event_bus=event_bus,
        safety_policies=[RateLimitSafetyPolicy(cooldown_seconds=1.0)],
        enabled=True,
    )

    request = OrchestrationRequest(
        source="voice",
        intent=VoiceIntent(intent=VoiceIntentType.COPY, text="copy"),
        raw_transcript="copy",
    )

    # First request passes
    resp1 = orchestrator.process_intent(request)
    assert resp1.status == "SUCCESS"

    # Immediate second request blocked by RateLimitSafetyPolicy
    resp2 = orchestrator.process_intent(request)
    assert resp2.status == "BLOCKED"
    assert resp2.success is False
    assert "Rate limit" in resp2.message
    assert len(blocked_events) == 1
    assert blocked_events[0].policy_name == "RateLimitSafetyPolicy"


def test_voice_pipeline_routes_through_brain_orchestrator():
    orchestrator = BrainOrchestrator(
        intent_manager=IntentManager(),
        context_manager=ContextManager(),
        automation_dispatcher=AutomationDispatcher(_FakeDesktop()),
        enabled=True,
    )

    pipeline = VoiceCommandPipeline(
        intent_parser=IntentParserService(),
        action_engine=_FakeActionEngine(),
        automation_dispatcher=AutomationDispatcher(_FakeDesktop()),
        orchestrator=orchestrator,
    )

    result = pipeline.execute("open chrome")
    assert result.success is True
    assert result.intent == "OPEN_CHROME"


def test_di_container_wires_brain_orchestrator():
    container = build_container(settings)
    assert container.brain_orchestrator is not None
    assert container.brain_orchestrator.enabled is True
