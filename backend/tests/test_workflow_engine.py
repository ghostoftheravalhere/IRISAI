"""Unit tests for Sprint 9 Task & Workflow Engine."""

from __future__ import annotations

from dataclasses import dataclass

from backend.automation.controller import DesktopController
from backend.automation.dispatcher import AutomationDispatcher, AutomationResult
from backend.brain.context_manager import ContextManager
from backend.brain.intent_manager import IntentManager
from backend.brain.orchestrator import BrainOrchestrator
from backend.brain.workflow import (
    CancellationToken,
    RetryPolicy,
    TaskPlan,
    WorkflowEngine,
    WorkflowStep,
)
from backend.brain.workflow_events import (
    WorkflowCompletedEvent,
    WorkflowFailedEvent,
    WorkflowStartedEvent,
    WorkflowStepCompletedEvent,
)
from backend.config.settings import settings
from backend.core.di.container import build_container
from backend.core.events.bus import EventBus
from backend.voice.command_parser import VoiceIntentType


class _FakeDesktop(DesktopController):
    def open_application(self, app_name: str) -> bool:
        return True

    def hotkey(self, *keys: str) -> bool:
        return True


def test_task_plan_sequential_execution():
    dispatcher = AutomationDispatcher(_FakeDesktop())
    engine = WorkflowEngine(automation_dispatcher=dispatcher, enabled=True)

    plan = TaskPlan(
        name="Sequential Test Plan",
        steps=[
            WorkflowStep(intent="OPEN_CHROME", target="chrome"),
            WorkflowStep(intent="COPY"),
        ],
    )

    success = engine.execute_plan(plan)
    assert success is True
    assert plan.steps[0].status == "COMPLETED"
    assert plan.steps[1].status == "COMPLETED"


def test_workflow_engine_event_bus_emissions():
    event_bus = EventBus()
    events_captured = []

    event_bus.subscribe(WorkflowStartedEvent, lambda e: events_captured.append(e))
    event_bus.subscribe(WorkflowStepCompletedEvent, lambda e: events_captured.append(e))
    event_bus.subscribe(WorkflowCompletedEvent, lambda e: events_captured.append(e))

    dispatcher = AutomationDispatcher(_FakeDesktop())
    engine = WorkflowEngine(automation_dispatcher=dispatcher, event_bus=event_bus, enabled=True)

    plan = TaskPlan(
        name="Event Bus Plan",
        steps=[
            WorkflowStep(intent="OPEN_CHROME"),
            WorkflowStep(intent="COPY"),
        ],
    )

    success = engine.execute_plan(plan)
    assert success is True
    assert len(events_captured) == 4
    assert isinstance(events_captured[0], WorkflowStartedEvent)
    assert isinstance(events_captured[1], WorkflowStepCompletedEvent)
    assert isinstance(events_captured[2], WorkflowStepCompletedEvent)
    assert isinstance(events_captured[3], WorkflowCompletedEvent)


def test_cancellation_token_interrupts_workflow():
    dispatcher = AutomationDispatcher(_FakeDesktop())
    event_bus = EventBus()
    failed_events = []
    event_bus.subscribe(WorkflowFailedEvent, lambda e: failed_events.append(e))

    engine = WorkflowEngine(automation_dispatcher=dispatcher, event_bus=event_bus, enabled=True)
    cancel_token = CancellationToken()
    cancel_token.cancel()  # Pre-cancel token

    plan = TaskPlan(
        name="Cancelled Plan",
        steps=[
            WorkflowStep(intent="OPEN_CHROME"),
        ],
    )

    success = engine.execute_plan(plan, cancel_token=cancel_token)
    assert success is False
    assert len(failed_events) == 1
    assert "Cancelled" in failed_events[0].reason


class _FailingDispatcher(AutomationDispatcher):
    def __init__(self, fail_after_step: int = 1):
        super().__init__(_FakeDesktop())
        self._count = 0
        self._fail_after = fail_after_step
        self.rolled_back_intents = []

    def dispatch(self, intent):
        self._count += 1
        if self._count > self._fail_after:
            self.rolled_back_intents.append(intent.intent.value)
            return AutomationResult(False, intent.intent, "Simulated failure")
        return AutomationResult(True, intent.intent, "Success")


def test_workflow_rollback_on_step_failure():
    dispatcher = _FailingDispatcher(fail_after_step=1)
    engine = WorkflowEngine(
        automation_dispatcher=dispatcher,
        retry_policy=RetryPolicy(max_retries=1, delay_seconds=0.01),
        enabled=True,
    )

    plan = TaskPlan(
        name="Rollback Test Plan",
        steps=[
            WorkflowStep(intent="OPEN_CHROME", rollback_intent="CLOSE_APPLICATION"),
            WorkflowStep(intent="COPY"),
        ],
    )

    success = engine.execute_plan(plan)
    assert success is False
    assert plan.steps[1].status == "FAILED"
    # Inverse rollback intent executed for step 0
    assert "CLOSE_APPLICATION" in dispatcher.rolled_back_intents


def test_brain_orchestrator_executes_task_plan():
    dispatcher = AutomationDispatcher(_FakeDesktop())
    engine = WorkflowEngine(automation_dispatcher=dispatcher, enabled=True)
    orchestrator = BrainOrchestrator(
        intent_manager=IntentManager(),
        context_manager=ContextManager(),
        automation_dispatcher=dispatcher,
        workflow_engine=engine,
        enabled=True,
    )

    plan = TaskPlan(name="Orchestrator Plan", steps=[WorkflowStep(intent="OPEN_CHROME")])
    success = orchestrator.execute_task_plan(plan)
    assert success is True


def test_di_container_wires_workflow_engine():
    container = build_container(settings)
    assert container.workflow_engine is not None
    assert container.workflow_engine.enabled is True
