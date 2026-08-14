"""Application service container factory.

Sprint 2 extracts service wiring from the FastAPI app without changing runtime
behavior or creating a global singleton.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.automation.controller import DesktopController
from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.context_manager import ContextManager
from backend.brain.context_store import ContextStore, InMemoryContextStore
from backend.brain.fusion import MultimodalFusionEngine
from backend.brain.intent_manager import IntentManager
from backend.brain.orchestrator import BrainOrchestrator
from backend.brain.planner import Planner
from backend.brain.reasoning.provider import MockPlannerProvider, OllamaPlannerProvider
from backend.brain.reasoning.service import ReasoningService
from backend.brain.skills.builtin import DesktopAutomationSkill, MediaControlSkill
from backend.brain.skills.registry import SkillRegistry
from backend.brain.workflow import RetryPolicy, WorkflowEngine
from backend.core.config.eye_config import EyeInteractionConfig
from backend.core.config.settings import Settings
from backend.core.events.bus import EventBus
from backend.eye_tracking.action_engine import ActionEngine
from backend.eye_tracking.blink_detection_service import BlinkDetectionService
from backend.eye_tracking.calibration import EyeCalibrationService
from backend.eye_tracking.camera_service import CameraService
from backend.eye_tracking.cursor_controller import CursorController
from backend.eye_tracking.debug_visualization_service import GazeDebugVisualizationService
from backend.eye_tracking.gaze_service import EyeGazeService
from backend.eye_tracking.gesture_interpreter_service import GestureInterpreterService
from backend.memory.session_memory import SessionMemory
from backend.platform.config_validator import ConfigurationValidator
from backend.platform.diagnostics import DiagnosticsService
from backend.platform.health import HealthMonitor, HealthState
from backend.platform.lifecycle import LifecycleManager, RecoveryManager
from backend.platform.metrics import MetricsRegistry, PerformanceMonitor
from backend.utils.logger import get_logger
from backend.voice.command_parser import IntentParserService
from backend.voice.pipeline import VoiceCommandPipeline
from backend.voice.preprocessor import AdaptiveGainControlFilter, AudioPreprocessor, PeakLimiterFilter
from backend.voice.recognizer import ListenMode, VoiceRecognitionConfig, VoiceRecognitionService
from backend.voice.telemetry import VoiceTelemetryService

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
    audio_preprocessor: AudioPreprocessor
    event_bus: EventBus
    voice_telemetry: VoiceTelemetryService
    brain_orchestrator: BrainOrchestrator
    context_store: ContextStore
    fusion_engine: MultimodalFusionEngine
    workflow_engine: WorkflowEngine
    skill_registry: SkillRegistry
    reasoning_service: ReasoningService
    health_monitor: HealthMonitor
    metrics_registry: MetricsRegistry
    diagnostics_service: DiagnosticsService
    lifecycle_manager: LifecycleManager
    recovery_manager: RecoveryManager
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

    event_bus = EventBus()
    voice_telemetry = VoiceTelemetryService(
        event_bus=event_bus,
        enabled=app_settings.TELEMETRY_ENABLED,
        capacity=app_settings.TELEMETRY_BUFFER_CAPACITY,
    )

    desktop_controller = DesktopController()
    automation_dispatcher = AutomationDispatcher(desktop_controller)
    intent_parser = IntentParserService()

    intent_manager = IntentManager()
    context_store = InMemoryContextStore(
        max_snapshots=app_settings.CONTEXT_STORE_MAX_SNAPSHOTS,
        ttl_seconds=app_settings.CONTEXT_TTL_SECONDS,
    )
    context_manager = ContextManager(store=context_store)

    workflow_engine = WorkflowEngine(
        automation_dispatcher=automation_dispatcher,
        event_bus=event_bus,
        retry_policy=RetryPolicy(max_retries=app_settings.WORKFLOW_MAX_RETRIES),
        enabled=app_settings.WORKFLOW_ENGINE_ENABLED,
    )

    skill_registry = SkillRegistry(
        event_bus=event_bus,
        strict_permissions=app_settings.STRICT_SKILL_PERMISSIONS,
        enabled=app_settings.SKILL_FRAMEWORK_ENABLED,
    )
    skill_registry.register_skill(DesktopAutomationSkill(automation_dispatcher))
    skill_registry.register_skill(MediaControlSkill(automation_dispatcher))

    planner_provider = (
        OllamaPlannerProvider(model_name=app_settings.LLM_MODEL, api_url=app_settings.LLM_API_URL)
        if app_settings.LLM_PROVIDER == "ollama"
        else MockPlannerProvider()
    )

    reasoning_service = ReasoningService(
        provider=planner_provider,
        skill_registry=skill_registry,
        context_manager=context_manager,
        event_bus=event_bus,
        enabled=app_settings.REASONING_ENABLED,
    )

    brain_orchestrator = BrainOrchestrator(
        intent_manager=intent_manager,
        context_manager=context_manager,
        automation_dispatcher=automation_dispatcher,
        event_bus=event_bus,
        workflow_engine=workflow_engine,
        reasoning_service=reasoning_service,
        enabled=app_settings.BRAIN_ORCHESTRATOR_ENABLED,
    )

    fusion_engine = MultimodalFusionEngine(
        window_ms=app_settings.FUSION_TEMPORAL_WINDOW_MS,
        min_confidence=app_settings.FUSION_MIN_CONFIDENCE,
        event_bus=event_bus,
        enabled=app_settings.FUSION_ENGINE_ENABLED,
    )

    voice_pipeline = VoiceCommandPipeline(
        intent_parser=intent_parser,
        action_engine=action_engine,
        automation_dispatcher=automation_dispatcher,
        event_bus=event_bus,
        orchestrator=brain_orchestrator,
        fusion_engine=fusion_engine,
    )

    audio_preprocessor = AudioPreprocessor(
        filters=[
            AdaptiveGainControlFilter(
                target_rms=app_settings.AGC_TARGET_RMS,
                min_gain=app_settings.AGC_MIN_GAIN,
                max_gain=app_settings.AGC_MAX_GAIN,
                enabled=app_settings.AGC_ENABLED,
            ),
            PeakLimiterFilter(
                threshold=app_settings.PEAK_LIMITER_THRESHOLD,
            ),
        ],
        enabled=app_settings.AUDIO_PREPROCESSOR_ENABLED,
    )

    default_listen_mode = _resolve_listen_mode(app_settings.VOICE_LISTEN_MODE)
    voice = VoiceRecognitionService(
        config=VoiceRecognitionConfig(
            model_size=app_settings.WHISPER_MODEL,
            sample_rate=app_settings.MIC_SAMPLE_RATE,
            listen_mode=default_listen_mode,
            enable_agc=app_settings.AGC_ENABLED,
            target_rms=app_settings.AGC_TARGET_RMS,
            max_agc_gain=app_settings.AGC_MAX_GAIN,
            preprocessor=audio_preprocessor,
            event_bus=event_bus,
        ),
        on_transcript=voice_pipeline.handle_transcript,
    )

    health_monitor = HealthMonitor(event_bus=event_bus, enabled=app_settings.RUNTIME_PLATFORM_ENABLED)
    metrics_registry = MetricsRegistry(enabled=app_settings.METRICS_ENABLED)
    performance_monitor = PerformanceMonitor(metrics_registry=metrics_registry, event_bus=event_bus)
    diagnostics_service = DiagnosticsService(health_monitor=health_monitor, metrics_registry=metrics_registry)
    lifecycle_manager = LifecycleManager(event_bus=event_bus)
    recovery_manager = RecoveryManager(event_bus=event_bus)

    # Register default health probes
    health_monitor.register_probe("voice_pipeline", lambda: (HealthState.HEALTHY, {"active": True}))
    health_monitor.register_probe(
        "brain_orchestrator",
        lambda: (HealthState.HEALTHY if brain_orchestrator.enabled else HealthState.DEGRADED, {"enabled": brain_orchestrator.enabled}),
    )
    health_monitor.register_probe(
        "workflow_engine",
        lambda: (HealthState.HEALTHY if workflow_engine.enabled else HealthState.DEGRADED, {"enabled": workflow_engine.enabled}),
    )
    health_monitor.register_probe(
        "skill_registry",
        lambda: (HealthState.HEALTHY if skill_registry.enabled else HealthState.DEGRADED, {"skills": len(skill_registry.discover_skills())}),
    )
    health_monitor.register_probe(
        "reasoning_service",
        lambda: (HealthState.HEALTHY if reasoning_service.enabled else HealthState.DEGRADED, {"enabled": reasoning_service.enabled}),
    )

    ConfigurationValidator.validate_settings(app_settings, event_bus=event_bus)

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
        audio_preprocessor=audio_preprocessor,
        event_bus=event_bus,
        voice_telemetry=voice_telemetry,
        brain_orchestrator=brain_orchestrator,
        context_store=context_store,
        fusion_engine=fusion_engine,
        workflow_engine=workflow_engine,
        skill_registry=skill_registry,
        reasoning_service=reasoning_service,
        health_monitor=health_monitor,
        metrics_registry=metrics_registry,
        diagnostics_service=diagnostics_service,
        lifecycle_manager=lifecycle_manager,
        recovery_manager=recovery_manager,
        voice=voice,
        intent_manager=intent_manager,
        context_manager=context_manager,
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
