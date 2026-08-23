"""Unit tests for Sprint 11 AI Reasoning & Planning Layer."""

from __future__ import annotations

from backend.automation.controller import DesktopController
from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.context_manager import ContextManager
from backend.brain.orchestrator import BrainOrchestrator
from backend.brain.reasoning.events import (
    ReasoningCompletedEvent,
    ReasoningFailedEvent,
    ReasoningStartedEvent,
)
from backend.brain.reasoning.prompt_builder import PromptBuilder
from backend.brain.reasoning.provider import MockPlannerProvider
from backend.brain.reasoning.service import ReasoningService
from backend.brain.reasoning.translator import PlanTranslator, PlanValidator
from backend.brain.skills.builtin import DesktopAutomationSkill, MediaControlSkill
from backend.brain.skills.registry import SkillRegistry
from backend.brain.workflow import WorkflowEngine
from backend.config.settings import settings
from backend.core.di.container import build_container
from backend.core.events.bus import EventBus


class _FakeDesktop(DesktopController):
    def open_application(self, app_name: str) -> bool:
        return True

    def hotkey(self, *keys: str) -> bool:
        return True

    def press(self, key: str, presses: int = 1) -> bool:
        return True

    def mute(self) -> bool:
        return True


def test_prompt_builder_formats_skill_catalog():
    dispatcher = AutomationDispatcher(_FakeDesktop())
    registry = SkillRegistry(enabled=True)
    registry.register_skill(DesktopAutomationSkill(dispatcher))

    prompt = PromptBuilder.build_prompt("open chrome", registry.discover_skills())
    assert "OPEN_CHROME" in prompt
    assert "open chrome" in prompt


def test_plan_translator_and_validator():
    dispatcher = AutomationDispatcher(_FakeDesktop())
    registry = SkillRegistry(enabled=True)
    registry.register_skill(DesktopAutomationSkill(dispatcher))

    provider = MockPlannerProvider()
    raw = provider.generate_plan("multi step task")

    plan = PlanTranslator.translate(raw)
    assert plan is not None
    assert len(plan.steps) == 2

    valid, _ = PlanValidator.validate_plan(plan, registry)
    assert valid is True


def test_plan_validator_rejects_hallucinated_skill():
    registry = SkillRegistry(enabled=True)

    provider = MockPlannerProvider()
    raw = provider.generate_plan("invalid hallucinated action")

    plan = PlanTranslator.translate(raw)
    assert plan is not None

    valid, reason = PlanValidator.validate_plan(plan, registry)
    assert valid is False
    assert "not registered" in reason


def test_reasoning_service_end_to_end_and_events():
    event_bus = EventBus()
    events_captured = []

    event_bus.subscribe(ReasoningStartedEvent, lambda e: events_captured.append(e))
    event_bus.subscribe(ReasoningCompletedEvent, lambda e: events_captured.append(e))

    dispatcher = AutomationDispatcher(_FakeDesktop())
    registry = SkillRegistry(event_bus=event_bus, enabled=True)
    registry.register_skill(DesktopAutomationSkill(dispatcher))

    service = ReasoningService(
        provider=MockPlannerProvider(),
        skill_registry=registry,
        event_bus=event_bus,
        enabled=True,
    )

    res = service.generate_plan("open chrome")
    assert res.success is True
    assert res.plan is not None
    assert len(events_captured) == 2
    assert isinstance(events_captured[0], ReasoningStartedEvent)
    assert isinstance(events_captured[1], ReasoningCompletedEvent)


def test_brain_orchestrator_reason_and_execute():
    dispatcher = AutomationDispatcher(_FakeDesktop())
    registry = SkillRegistry(enabled=True)
    registry.register_skill(DesktopAutomationSkill(dispatcher))

    engine = WorkflowEngine(automation_dispatcher=dispatcher, enabled=True)
    reasoning_service = ReasoningService(
        provider=MockPlannerProvider(),
        skill_registry=registry,
        enabled=True,
    )

    orchestrator = BrainOrchestrator(
        intent_manager=None,
        context_manager=ContextManager(),
        automation_dispatcher=dispatcher,
        workflow_engine=engine,
        reasoning_service=reasoning_service,
        enabled=True,
    )

    success = orchestrator.reason_and_execute("open chrome")
    assert success is True


def test_di_container_wires_reasoning_service():
    container = build_container(settings)
    assert container.reasoning_service is not None
    assert container.reasoning_service.enabled is True
