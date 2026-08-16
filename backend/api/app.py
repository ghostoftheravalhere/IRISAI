"""
FastAPI Application Factory
Creates and configures the FastAPI app with all routers and middleware.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import (
    agent_routes,
    auth_routes,
    camera,
    dialogue_routes,
    eye,
    gaze_dataset_routes,
    goal_routes,
    health,
    learning_routes,
    memory_routes,
    native_app_routes,
    nlu_routes,
    preview_routes,
    recovery_routes,
    runtime_routes,
    streaming_routes,
    uia_routes,
    verification_routes,
    vision_action_routes,
    vision_routes,
    voice,
    wakeword_routes,
    world_routes,
    workspace_routes,
)
from backend.config.settings import settings
from backend.core.di.container import AppContainer, build_container
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI application lifespan context manager for startup and shutdown actions."""
    eye_config = getattr(app.state, "eye_interaction_config", None)
    logger.info("IRIS AI backend started - v%s [%s]", settings.APP_VERSION, settings.APP_ENV)
    if eye_config:
        logger.info(
            "Eye interaction ready: intentional blink %.0f-%.0f ms, confidence threshold %.2f",
            eye_config.intentional_blink_min_ms,
            eye_config.intentional_blink_max_ms,
            eye_config.tracking_confidence_threshold,
        )
    logger.info(
        "Voice command pipeline ready (Whisper model=%s, sample_rate=%s)",
        settings.WHISPER_MODEL,
        settings.MIC_SAMPLE_RATE,
    )
    if hasattr(app.state, "lifecycle_manager"):
        app.state.lifecycle_manager.startup()

    yield

    # Ensure webcam and voice streams are released cleanly upon server shutdown.
    if hasattr(app.state, "lifecycle_manager"):
        app.state.lifecycle_manager.shutdown(reason="server_shutdown")
    if hasattr(app.state, "voice") and app.state.voice is not None:
        app.state.voice.stop()
    if hasattr(app.state, "camera") and app.state.camera is not None:
        app.state.camera.cleanup()
    logger.info("IRIS AI backend shut down cleanly.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="IRIS AI Backend",
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    container = build_container(settings)
    _attach_container(app, container)

    app.include_router(health.router)
    app.include_router(camera.router)
    app.include_router(eye.router, prefix="/eye")
    app.include_router(voice.router, prefix="/voice")
    app.include_router(vision_routes.router, prefix="/api/v1")
    app.include_router(memory_routes.router, prefix="/api/v1")
    app.include_router(dialogue_routes.router, prefix="/api/v1")
    app.include_router(workspace_routes.router, prefix="/api/v1")
    app.include_router(goal_routes.router, prefix="/api/v1")
    app.include_router(wakeword_routes.router, prefix="/api/v1")
    app.include_router(vision_action_routes.router, prefix="/api/v1")
    app.include_router(native_app_routes.router, prefix="/api/v1")
    app.include_router(nlu_routes.router, prefix="/api/v1")
    app.include_router(streaming_routes.router, prefix="/api/v1")
    app.include_router(learning_routes.router, prefix="/api/v1")
    app.include_router(agent_routes.router, prefix="/api/v1")
    app.include_router(verification_routes.router, prefix="/api/v1")
    app.include_router(uia_routes.router, prefix="/api/v1")
    app.include_router(preview_routes.router, prefix="/api/v1")
    app.include_router(recovery_routes.router, prefix="/api/v1")
    app.include_router(world_routes.router, prefix="/api/v1")
    app.include_router(runtime_routes.router, prefix="/api/v1")
    app.include_router(gaze_dataset_routes.router, prefix="/api/v1")
    app.include_router(auth_routes.router)
    app.include_router(auth_routes.github_router)

    @app.get("/api/v1/health")
    async def get_health_status():
        """Return runtime platform component health status and diagnostics."""
        if hasattr(app.state, "diagnostics_service"):
            return app.state.diagnostics_service.generate_snapshot()
        return {"status": "ok"}

    @app.get("/api/v1/metrics")
    async def get_metrics_summary():
        """Return operational metrics summary."""
        if hasattr(app.state, "metrics_registry"):
            return app.state.metrics_registry.get_metrics_summary()
        return {}

    return app


def _attach_container(app: FastAPI, container: AppContainer) -> None:
    """Attach DI services using the existing public app.state names."""
    app.state.eye_interaction_config = container.eye_interaction_config
    app.state.camera = container.camera
    app.state.eye_calibration = container.eye_calibration
    app.state.eye_gaze = container.eye_gaze
    app.state.blink_detection = container.blink_detection
    app.state.gesture_interpreter = container.gesture_interpreter
    app.state.action_engine = container.action_engine
    app.state.cursor_controller = container.cursor_controller
    app.state.gaze_debug_visualizer = container.gaze_debug_visualizer
    app.state.desktop_controller = container.desktop_controller
    app.state.automation_dispatcher = container.automation_dispatcher
    app.state.intent_parser = container.intent_parser
    app.state.voice_pipeline = container.voice_pipeline
    app.state.audio_preprocessor = container.audio_preprocessor
    app.state.event_bus = container.event_bus
    app.state.voice_telemetry = container.voice_telemetry
    app.state.brain_orchestrator = container.brain_orchestrator
    app.state.context_store = container.context_store
    app.state.fusion_engine = container.fusion_engine
    app.state.workflow_engine = container.workflow_engine
    app.state.skill_registry = container.skill_registry
    app.state.reasoning_service = container.reasoning_service
    app.state.health_monitor = container.health_monitor
    app.state.metrics_registry = container.metrics_registry
    app.state.diagnostics_service = container.diagnostics_service
    app.state.lifecycle_manager = container.lifecycle_manager
    app.state.recovery_manager = container.recovery_manager
    app.state.voice = container.voice
