"""Sprint 2 tests for DI extraction, Brain stubs, and Memory stub."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.app import _attach_container, create_app
from backend.config.settings import settings
from backend.core.contracts.action import ActionType
from backend.core.contracts.intent import Confidence, IntentSource
from backend.core.di.container import build_container
from backend.memory.session_memory import SessionMemory


APP_STATE_NAMES = (
    "eye_interaction_config",
    "camera",
    "eye_calibration",
    "eye_gaze",
    "blink_detection",
    "gesture_interpreter",
    "action_engine",
    "cursor_controller",
    "gaze_debug_visualizer",
    "desktop_controller",
    "automation_dispatcher",
    "intent_parser",
    "voice_pipeline",
    "audio_preprocessor",
    "event_bus",
    "voice_telemetry",
    "brain_orchestrator",
    "context_store",
    "fusion_engine",
    "workflow_engine",
    "skill_registry",
    "reasoning_service",
    "health_monitor",
    "metrics_registry",
    "diagnostics_service",
    "lifecycle_manager",
    "recovery_manager",
    "voice",
)


def test_build_container_returns_fresh_services() -> None:
    first = build_container(settings)
    second = build_container(settings)

    try:
        assert first is not second
        assert first.camera is not second.camera
        assert first.voice is not second.voice
        assert first.eye_interaction_config.overlay_mode in {"normal", "debug"}
    finally:
        first.voice.stop()
        first.camera.cleanup()
        second.voice.stop()
        second.camera.cleanup()


def test_container_attaches_existing_app_state_names() -> None:
    app = FastAPI()
    container = build_container(settings)

    try:
        _attach_container(app, container)
        for name in APP_STATE_NAMES:
            assert hasattr(app.state, name), name
        assert app.state.camera is container.camera
        assert app.state.voice is container.voice
    finally:
        container.voice.stop()
        container.camera.cleanup()


def test_create_app_preserves_health_response_shape() -> None:
    app = create_app()
    try:
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {
                "status": "online",
                "version": settings.APP_VERSION,
            }
    finally:
        app.state.voice.stop()
        app.state.camera.cleanup()


def test_brain_stubs_use_sprint1_contracts_without_business_logic() -> None:
    container = build_container(settings)

    try:
        intent = container.intent_manager.create_intent(
            name="TEST_INTENT",
            source=IntentSource.SYSTEM,
            confidence=Confidence(0.75),
            payload={"value": 1},
        )
        assert container.intent_manager.pass_through(intent) is intent

        context = container.context_manager.get_context()
        assert context.data == {}
        assert container.context_manager.pass_through(context) is context

        plan = container.planner.plan(intent)
        assert len(plan.actions) == 1
        assert plan.actions[0].action_type == ActionType.NO_ACTION
        assert plan.actions[0].name == "TEST_INTENT"
        assert plan.actions[0].payload == {"value": 1}
    finally:
        container.voice.stop()
        container.camera.cleanup()


def test_session_memory_is_bounded_and_in_memory() -> None:
    memory = SessionMemory(max_events=2)
    memory.append("first")
    memory.append("second")
    memory.append("third")

    assert memory.get_events() == ("second", "third")
    assert len(memory) == 2

    memory.clear()
    assert memory.get_events() == ()
