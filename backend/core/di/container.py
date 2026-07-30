"""Application service container factory.

Sprint 2 extracts service wiring from the FastAPI app without changing runtime
behavior or creating a global singleton.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.automation.controller import DesktopController
from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.context_manager import ContextManager
from backend.brain.intent_manager import IntentManager
from backend.brain.planner import Planner
from backend.core.config.eye_config import EyeInteractionConfig
from backend.core.config.settings import Settings
from backend.eye_tracking.action_engine import ActionEngine
from backend.eye_tracking.blink_detection_service import BlinkDetectionService
from backend.eye_tracking.calibration import EyeCalibrationService
from backend.eye_tracking.camera_service import CameraService
from backend.eye_tracking.cursor_controller import CursorController
from backend.eye_tracking.debug_visualization_service import GazeDebugVisualizationService
from backend.eye_tracking.gaze_service import EyeGazeService
from backend.eye_tracking.gesture_interpreter_service import GestureInterpreterService
from backend.memory.session_memory import SessionMemory
from backend.utils.logger import get_logger
from backend.voice.command_parser import IntentParserService
from backend.voice.pipeline import VoiceCommandPipeline
from backend.voice.recognizer import ListenMode, VoiceRecognitionConfig, VoiceRecognitionService

logger = get_logger(__name__)


@dataclass(frozen=True)
class AppContainer:
    """Freshly built application services.

    Existing field names mirror ``app.state`` names where services are already
    part of the public runtime contract.
    """

    eye_interaction_config: EyeInteractionConfig
    camera: CameraService
    eye_calibration: EyeCalibrationService
    eye_gaze: EyeGazeService
    blink_detection: BlinkDetectionService
    gesture_interpreter: GestureInterpreterService
    action_engine: ActionEngine
    cursor_controller: CursorController
    gaze_debug_visualizer: GazeDebugVisualizationService
    desktop_controller: DesktopController
    automation_dispatcher: AutomationDispatcher
    intent_parser: IntentParserService
    voice_pipeline: VoiceCommandPipeline
    voice: VoiceRecognitionService
    intent_manager: IntentManager
    context_manager: ContextManager
    planner: Planner
    session_memory: SessionMemory


def build_container(app_settings: Settings) -> AppContainer:
    """Build and wire a fresh set of application services."""
    eye_config = _build_eye_interaction_config(app_settings)

    camera = CameraService(
        camera_index=app_settings.WEBCAM_INDEX,
        eye_config=eye_config,
    )
    eye_calibration = EyeCalibrationService(eye_config=eye_config)
    eye_gaze = EyeGazeService(
        camera_service=camera,
        calibration_service=eye_calibration,
        eye_config=eye_config,
    )
    blink_detection = BlinkDetectionService(config=eye_config)
    gesture_interpreter = GestureInterpreterService(config=eye_config)
    action_engine = ActionEngine(eye_config=eye_config)
    cursor_controller = CursorController(
        gaze_service=eye_gaze,
        eye_config=eye_config,
    )
    camera.configure_blink_detection(
        blink_detection_service=blink_detection,
        gesture_interpreter_service=gesture_interpreter,
        action_engine=action_engine,
        cursor_controller=cursor_controller,
    )
    gaze_debug_visualizer = GazeDebugVisualizationService(
        overlay_mode=eye_config.overlay_mode,
    )
    camera.configure_gaze_debug_visualization(
        gaze_service=eye_gaze,
        calibration_service=eye_calibration,
        debug_visualizer=gaze_debug_visualizer,
    )

    desktop_controller = DesktopController()
    automation_dispatcher = AutomationDispatcher(desktop_controller)
    intent_parser = IntentParserService()
    voice_pipeline = VoiceCommandPipeline(
        intent_parser=intent_parser,
        action_engine=action_engine,
        automation_dispatcher=automation_dispatcher,
    )

    default_listen_mode = _resolve_listen_mode(app_settings.VOICE_LISTEN_MODE)
    voice = VoiceRecognitionService(
        config=VoiceRecognitionConfig(
            model_size=app_settings.WHISPER_MODEL,
            sample_rate=app_settings.MIC_SAMPLE_RATE,
            listen_mode=default_listen_mode,
        ),
        on_transcript=voice_pipeline.handle_transcript,
    )

    return AppContainer(
        eye_interaction_config=eye_config,
        camera=camera,
        eye_calibration=eye_calibration,
        eye_gaze=eye_gaze,
        blink_detection=blink_detection,
        gesture_interpreter=gesture_interpreter,
        action_engine=action_engine,
        cursor_controller=cursor_controller,
        gaze_debug_visualizer=gaze_debug_visualizer,
        desktop_controller=desktop_controller,
        automation_dispatcher=automation_dispatcher,
        intent_parser=intent_parser,
        voice_pipeline=voice_pipeline,
        voice=voice,
        intent_manager=IntentManager(),
        context_manager=ContextManager(),
        planner=Planner(),
        session_memory=SessionMemory(),
    )


def _build_eye_interaction_config(app_settings: Settings) -> EyeInteractionConfig:
    """Build shared eye interaction thresholds from application settings."""
    config = EyeInteractionConfig(
        ear_close_threshold=app_settings.EAR_CLOSE_THRESHOLD,
        ear_open_threshold=app_settings.EAR_OPEN_THRESHOLD,
        intentional_blink_min_ms=app_settings.INTENTIONAL_BLINK_MIN_MS,
        intentional_blink_max_ms=app_settings.INTENTIONAL_BLINK_MAX_MS,
        double_long_blink_window_ms=app_settings.DOUBLE_LONG_BLINK_WINDOW_MS,
        cursor_sensitivity=app_settings.CURSOR_SENSITIVITY,
        cursor_smoothing_alpha=app_settings.CURSOR_SMOOTHING,
        cursor_dead_zone_px=app_settings.CURSOR_DEAD_ZONE_PX,
        cursor_min_move_px=app_settings.CURSOR_MIN_MOVE_PX,
        cursor_max_step_px=app_settings.CURSOR_MAX_STEP_PX,
        gaze_smoothing_alpha=app_settings.GAZE_SMOOTHING,
        tracking_confidence_threshold=app_settings.TRACKING_CONFIDENCE_THRESHOLD,
        calibration_quality_threshold=app_settings.CALIBRATION_QUALITY_THRESHOLD,
        calibration_rmse_scale=app_settings.CALIBRATION_RMSE_SCALE,
        calibration_good_score_threshold=app_settings.CALIBRATION_GOOD_SCORE_THRESHOLD,
        overlay_mode=app_settings.OVERLAY_MODE.lower().strip(),
    )
    config.validate()
    return config


def _resolve_listen_mode(raw_mode: str) -> ListenMode:
    """Resolve configured voice listen mode without raising during startup."""
    listen_mode_raw = raw_mode.strip().lower().replace("-", "_")
    try:
        return ListenMode(listen_mode_raw)
    except ValueError:
        logger.warning("Invalid VOICE_LISTEN_MODE=%s; defaulting to continuous.", raw_mode)
        return ListenMode.CONTINUOUS
