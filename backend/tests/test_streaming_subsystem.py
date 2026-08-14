"""Unit tests for Streaming Intelligence & Interruptible Conversation Subsystem."""

from __future__ import annotations

from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.streaming_planner import StreamingPlanner
from backend.brain.workflow import TaskPlan, WorkflowEngine, WorkflowStep
from backend.core.events.bus import EventBus
from backend.voice.conversation_streamer import ConversationStreamer
from backend.voice.incremental_reasoner import IncrementalReasoner
from backend.voice.streaming_events import PartialTranscriptEvent, WorkflowMutatedEvent
from backend.voice.streaming_speech_session import StreamingSpeechSession


def test_streaming_speech_session():
    event_bus = EventBus()
    events_received = []

    def _on_event(e):
        events_received.append(e)

    event_bus.subscribe(PartialTranscriptEvent, _on_event)

    session = StreamingSpeechSession(event_bus=event_bus)
    session.start_session()

    f1 = session.process_chunk("Open Chrome")
    assert f1.text == "Open Chrome"
    assert f1.is_final is False
    assert len(events_received) == 1

    final_text = session.end_session()
    assert final_text == "Open Chrome"


def test_incremental_reasoner_self_correction():
    reasoner = IncrementalReasoner()

    # Mid-utterance correction: "Open Chrome... actually Edge... search ChatGPT"
    p1 = reasoner.predict_partial("Open Chrome actually Edge search ChatGPT")
    assert p1.intent_name in ("OPEN_APPLICATION", "BROWSER_SEARCH")
    assert p1.target == "edge"


def test_streaming_planner_plan_replacement():
    event_bus = EventBus()
    events_received = []

    def _on_event(e):
        events_received.append(e)

    event_bus.subscribe(WorkflowMutatedEvent, _on_event)

    dispatcher = AutomationDispatcher(None)
    workflow_engine = WorkflowEngine(automation_dispatcher=dispatcher, enabled=True)
    planner = StreamingPlanner(workflow_engine=workflow_engine, event_bus=event_bus)

    plan1 = TaskPlan(name="Plan 1", steps=[WorkflowStep(intent="OPEN_APPLICATION", target="chrome")])
    plan2 = TaskPlan(name="Plan 2", steps=[WorkflowStep(intent="OPEN_APPLICATION", target="edge")])

    planner.replace_plan(plan1)
    assert planner.active_plan.name == "Plan 1"

    planner.replace_plan(plan2)
    assert planner.active_plan.name == "Plan 2"
    assert len(events_received) == 2


def test_conversation_streamer():
    streamer = ConversationStreamer()
    streamer.session.start_session()

    telemetry = streamer.process_live_chunk("Launch Chrome")
    assert telemetry["text"] == "Launch Chrome"
    assert telemetry["target"] == "chrome"
