"""
FastAPI Application Factory
Creates and configures the FastAPI app with all routers and middleware.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import camera, eye, health, voice
from backend.config.settings import settings
from backend.core.di.container import AppContainer, build_container
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="IRIS AI Backend",
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.DEBUG else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    container = build_container(settings)
    _attach_container(app, container)
    eye_config = container.eye_interaction_config

    app.include_router(health.router)
    app.include_router(camera.router)
    app.include_router(eye.router, prefix="/eye")
    app.include_router(voice.router, prefix="/voice")

    @app.on_event("startup")
    async def on_startup():
        logger.info("IRIS AI backend started - v%s [%s]", settings.APP_VERSION, settings.APP_ENV)
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

    @app.on_event("shutdown")
    async def on_shutdown():
        # Ensure the webcam is released even if the client never called /camera/stop.
        app.state.voice.stop()
        app.state.camera.cleanup()
        logger.info("IRIS AI backend shut down cleanly.")

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
    app.state.voice = container.voice
