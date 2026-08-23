"""Unit tests for Sprint 7 Context & Memory Subsystem."""

from __future__ import annotations

from dataclasses import dataclass
import time

from backend.automation.controller import DesktopController
from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.context_manager import ContextManager
from backend.brain.context_store import ContextSnapshot, InMemoryContextStore
from backend.brain.intent_manager import IntentManager
from backend.brain.orchestrator import BrainOrchestrator, OrchestrationRequest
from backend.config.settings import settings
from backend.core.di.container import build_container
from backend.voice.command_parser import VoiceIntent, VoiceIntentType


class _FakeDesktop(DesktopController):
    def open_application(self, app_name: str) -> bool:
        return True

    def hotkey(self, *keys: str) -> bool:
        return True


def test_context_snapshot_instantiation():
    snap = ContextSnapshot(session_id="session_1", intent="OPEN_CHROME", raw_transcript="open chrome")
    assert snap.session_id == "session_1"
    assert snap.intent == "OPEN_CHROME"
    assert snap.raw_transcript == "open chrome"
    assert snap.snapshot_id is not None
    assert snap.timestamp > 0.0


def test_in_memory_context_store_save_get_latest_and_history():
    store = InMemoryContextStore(max_snapshots=10, ttl_seconds=60.0)

    snap1 = ContextSnapshot(session_id="s1", intent="COPY", raw_transcript="copy")
    snap2 = ContextSnapshot(session_id="s1", intent="PASTE", raw_transcript="paste")
    snap_other = ContextSnapshot(session_id="s2", intent="MUTE", raw_transcript="mute")

    store.save_snapshot(snap1)
    store.save_snapshot(snap2)
    store.save_snapshot(snap_other)

    latest_s1 = store.get_latest("s1")
    assert latest_s1 is not None
    assert latest_s1.intent == "PASTE"

    history_s1 = store.get_history("s1", limit=10)
    assert len(history_s1) == 2
    assert [s.intent for s in history_s1] == ["COPY", "PASTE"]

    latest_s2 = store.get_latest("s2")
    assert latest_s2 is not None
    assert latest_s2.intent == "MUTE"


def test_in_memory_context_store_capacity_eviction():
    store = InMemoryContextStore(max_snapshots=3, ttl_seconds=60.0)

    for i in range(5):
        store.save_snapshot(ContextSnapshot(session_id="s1", raw_transcript=f"cmd_{i}"))

    history = store.get_history("s1", limit=10)
    assert len(history) == 3
    assert [s.raw_transcript for s in history] == ["cmd_2", "cmd_3", "cmd_4"]


def test_in_memory_context_store_ttl_expiration():
    store = InMemoryContextStore(max_snapshots=10, ttl_seconds=0.1)

    snap = ContextSnapshot(session_id="s1", raw_transcript="stale command")
    store.save_snapshot(snap)

    assert store.get_latest("s1") is not None

    # Wait for TTL to expire
    time.sleep(0.15)

    assert store.get_latest("s1") is None
    assert store.get_history("s1") == []


def test_context_manager_integration():
    store = InMemoryContextStore()
    manager = ContextManager(store=store)

    snap = manager.record_utterance("open chrome", intent="OPEN_CHROME", active_app="Chrome")
    assert snap.intent == "OPEN_CHROME"

    current = manager.get_current_context()
    assert current["hasContext"] is True
    assert current["latest"].intent == "OPEN_CHROME"

    history = manager.get_recent_history()
    assert len(history) == 1


def test_brain_orchestrator_records_context_snapshot():
    store = InMemoryContextStore()
    manager = ContextManager(store=store)
    orchestrator = BrainOrchestrator(
        intent_manager=IntentManager(),
        context_manager=manager,
        automation_dispatcher=AutomationDispatcher(_FakeDesktop()),
        enabled=True,
    )

    request = OrchestrationRequest(
        source="voice",
        intent=VoiceIntent(intent=VoiceIntentType.OPEN_CHROME, text="open chrome"),
        raw_transcript="open chrome",
    )

    response = orchestrator.process_intent(request)
    assert response.success is True

    latest = store.get_latest()
    assert latest is not None
    assert latest.intent == "OPEN_CHROME"
    assert latest.raw_transcript == "open chrome"


def test_di_container_wires_context_store():
    container = build_container(settings)
    assert container.context_store is not None
    assert container.context_manager.store is container.context_store
