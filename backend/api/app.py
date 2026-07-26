"""
FastAPI Application Factory
Creates and configures the FastAPI app with all routers and middleware.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import camera, eye, health, voice
from backend.automation.controller import DesktopController
from backend.automation.dispatcher import AutomationDispatcher
from backend.config.settings import settings
from backend.eye_tracking.action_engine import ActionEngine
from backend.eye_tracking.blink_detection_service import BlinkDetectionService
from backend.eye_tracking.calibration import EyeCalibrationService
from backend.eye_tracking.camera_service import CameraService
from backend.eye_tracking.cursor_controller import CursorController
from backend.eye_tracking.debug_visualization_service import GazeDebugVisualizationService
from backend.eye_tracking.eye_interaction_config import EyeInteractionConfig
from backend.eye_tracking.gaze_service import EyeGazeService
from backend.eye_tracking.gesture_interpreter_service import GestureInterpreterService
from backend.utils.logger import get_logger
from backend.voice.command_parser import IntentParserService
from backend.voice.pipeline import VoiceCommandPipeline
from backend.voice.recognizer import ListenMode, VoiceRecognitionConfig, VoiceRecognitionService

logger = get_logger(__name__)


def _build_eye_interaction_config() -> EyeInteractionConfig:
    """Build shared eye interaction thresholds from application settings."""
    config = EyeInteractionConfig(
        ear_close_threshold=settings.EAR_CLOSE_THRESHOLD,
        ear_open_threshold=settings.EAR_OPEN_THRESHOLD,
        intentional_blink_min_ms=settings.INTENTIONAL_BLINK_MIN_MS,
        intentional_blink_max_ms=settings.INTENTIONAL_BLINK_MAX_MS,
        double_long_blink_window_ms=settings.DOUBLE_LONG_BLINK_WINDOW_MS,
        cursor_sensitivity=settings.CURSOR_SENSITIVITY,
        cursor_smoothing_alpha=settings.CURSOR_SMOOTHING,
        cursor_dead_zone_px=settings.CURSOR_DEAD_ZONE_PX,
        cursor_min_move_px=settings.CURSOR_MIN_MOVE_PX,
        cursor_max_step_px=settings.CURSOR_MAX_STEP_PX,
        gaze_smoothing_alpha=settings.GAZE_SMOOTHING,
        tracking_confidence_threshold=settings.TRACKING_CONFIDENCE_THRESHOLD,
        calibration_quality_threshold=settings.CALIBRATION_QUALITY_THRESHOLD,
        calibration_rmse_scale=settings.CALIBRATION_RMSE_SCALE,
        calibration_good_score_threshold=settings.CALIBRATION_GOOD_SCORE_THRESHOLD,
        overlay_mode=settings.OVERLAY_MODE.lower().strip(),
    )
    config.validate()
    return config


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

    eye_config = _build_eye_interaction_config()
    app.state.eye_interaction_config = eye_config

    # Shared service instances — attached to app.state for request access
    app.state.camera = CameraService(
        camera_index=settings.WEBCAM_INDEX,
        eye_config=eye_config,
    )
    app.state.eye_calibration = EyeCalibrationService(eye_config=eye_config)
    app.state.eye_gaze = EyeGazeService(
        camera_service=app.state.camera,
        calibration_service=app.state.eye_calibration,
        eye_config=eye_config,
    )
    app.state.blink_detection = BlinkDetectionService(config=eye_config)
    app.state.gesture_interpreter = GestureInterpreterService(config=eye_config)
    app.state.action_engine = ActionEngine(eye_config=eye_config)
    app.state.cursor_controller = CursorController(
        gaze_service=app.state.eye_gaze,
        eye_config=eye_config,
    )
    app.state.camera.configure_blink_detection(
        blink_detection_service=app.state.blink_detection,
        gesture_interpreter_service=app.state.gesture_interpreter,
        action_engine=app.state.action_engine,
        cursor_controller=app.state.cursor_controller,
    )
    app.state.gaze_debug_visualizer = GazeDebugVisualizationService(
        overlay_mode=eye_config.overlay_mode,
    )
    app.state.camera.configure_gaze_debug_visualization(
        gaze_service=app.state.eye_gaze,
        calibration_service=app.state.eye_calibration,
        debug_visualizer=app.state.gaze_debug_visualizer,
    )

    # Voice → IntentParser → ActionEngine → DesktopController
    app.state.desktop_controller = DesktopController()
    app.state.automation_dispatcher = AutomationDispatcher(app.state.desktop_controller)
    app.state.intent_parser = IntentParserService()
    app.state.voice_pipeline = VoiceCommandPipeline(
        intent_parser=app.state.intent_parser,
        action_engine=app.state.action_engine,
        automation_dispatcher=app.state.automation_dispatcher,
    )
    listen_mode_raw = settings.VOICE_LISTEN_MODE.strip().lower().replace("-", "_")
    try:
        default_listen_mode = ListenMode(listen_mode_raw)
    except ValueError:
        logger.warning("Invalid VOICE_LISTEN_MODE=%s; defaulting to continuous.", settings.VOICE_LISTEN_MODE)
        default_listen_mode = ListenMode.CONTINUOUS

    app.state.voice = VoiceRecognitionService(
        config=VoiceRecognitionConfig(
            model_size=settings.WHISPER_MODEL,
            sample_rate=settings.MIC_SAMPLE_RATE,
            listen_mode=default_listen_mode,
        ),
        on_transcript=app.state.voice_pipeline.handle_transcript,
    )

    app.include_router(health.router)
    app.include_router(camera.router)
    app.include_router(eye.router, prefix="/eye")
    app.include_router(voice.router, prefix="/voice")

    @app.on_event("startup")
    async def on_startup():
        logger.info("IRIS AI backend started — v%s [%s]", settings.APP_VERSION, settings.APP_ENV)
        logger.info(
            "Eye interaction ready: intentional blink %.0f–%.0f ms, confidence threshold %.2f",
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
        # Ensure the webcam is released even if the client never called /camera/stop
        app.state.voice.stop()
        app.state.camera.cleanup()
        logger.info("IRIS AI backend shut down cleanly.")

    return app
