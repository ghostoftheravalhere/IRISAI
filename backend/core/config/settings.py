"""
Application Settings
Loaded from .env file via pydantic-settings.
Import: from backend.core.config.settings import settings
"""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def get_app_data_dir() -> Path:
    """Uses %LOCALAPPDATA%/IRISAI on Windows, ~/.irisai on Unix."""
    base = os.getenv("LOCALAPPDATA")
    data_dir = Path(base) / "IRISAI" if base else Path.home() / ".irisai"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return data_dir


APP_DATA_DIR: Path = get_app_data_dir()
DATASET_DIR: Path = APP_DATA_DIR / "dataset"
LOGS_DIR: Path = APP_DATA_DIR / "logs"
RECORDINGS_DIR: Path = APP_DATA_DIR / "recordings"
CALIBRATION_DIR: Path = APP_DATA_DIR / "calibration"

for _target_dir in (DATASET_DIR, LOGS_DIR, RECORDINGS_DIR, CALIBRATION_DIR):
    try:
        _target_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_ENV: str = "development"
    APP_VERSION: str = "2.5.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./iris_ai.db"

    # Gemini AI
    GEMINI_API_KEY: str = ""

    # Eye Tracking / accessibility interaction
    WEBCAM_INDEX: int = 0
    KINEMATIC_PHYSICS_ENABLED: bool = True
    KINEMATIC_STIFFNESS: float = 160.0
    KINEMATIC_DAMPING: float = 25.3
    KINEMATIC_DAMPING_RATIO: float = 1.0
    KINEMATIC_MASS: float = 1.0
    KINEMATIC_TREMOR_REDUCTION_PX: float = 14.0
    KINEMATIC_DEADBAND_RADIUS: float = 18.0
    KINEMATIC_BREAKOUT_RADIUS: float = 25.0
    KINEMATIC_ANCHOR_VELOCITY_THRESHOLD: float = 15.0
    KINEMATIC_ACCELERATION_GAIN: float = 1.5
    KINEMATIC_MAX_VELOCITY_PX_S: float = 12000.0
    GAZE_GAIN_X: float = 3.6
    GAZE_GAIN_Y: float = 3.2
    GAZE_NEUTRAL_X: float = 0.50
    GAZE_NEUTRAL_Y: float = 0.58
    GAZE_VERTICAL_DEADZONE: float = 0.0
    GAZE_SMOOTHING: float = 0.28
    EAR_CLOSE_THRESHOLD: float = 0.16
    EAR_OPEN_THRESHOLD: float = 0.21
    EAR_FREEZE_THRESHOLD: float = 0.19
    INTENTIONAL_BLINK_MIN_MS: float = 400.0
    INTENTIONAL_BLINK_MAX_MS: float = 1200.0
    DOUBLE_LONG_BLINK_WINDOW_MS: float = 400.0
    CURSOR_SENSITIVITY: float = 1.0
    CURSOR_SMOOTHING: float = 0.20
    CURSOR_DEAD_ZONE_PX: float = 15.0
    CURSOR_MIN_MOVE_PX: float = 2.5
    CURSOR_MAX_STEP_PX: float = 1200.0
    TRACKING_CONFIDENCE_THRESHOLD: float = 0.45
    CALIBRATION_QUALITY_THRESHOLD: float = 0.45
    CALIBRATION_RMSE_SCALE: float = 5.0
    CALIBRATION_GOOD_SCORE_THRESHOLD: float = 0.58
    OVERLAY_MODE: str = "normal"

    # Voice
    WHISPER_MODEL: str = "small.en"
    VOICE_MODEL_PATH: str | None = None
    VOSK_MODEL_PATH: str | None = None
    MIC_SAMPLE_RATE: int = 16000
    VOICE_LISTEN_MODE: str = "continuous"
    VOICE_OUTPUT_ENABLED: bool = False  # V2.4 Submission Stability Mode (Voice Input Active, Spoken Output Disabled)
    ENABLE_AGC: bool = True
    AUDIO_PREPROCESSOR_ENABLED: bool = True
    AGC_ENABLED: bool = True
    AGC_TARGET_RMS: float = 0.04
    AGC_MIN_GAIN: float = 0.5
    AGC_MAX_GAIN: float = 8.0
    PEAK_LIMITER_THRESHOLD: float = 0.95
    NO_SPEECH_THRESHOLD: float = 0.80
    LOGPROB_THRESHOLD: float = -1.0

    # Telemetry & Events
    TELEMETRY_ENABLED: bool = True
    TELEMETRY_BUFFER_CAPACITY: int = 100

    # Brain Orchestrator & Context
    BRAIN_ORCHESTRATOR_ENABLED: bool = True
    SAFETY_VALIDATION_ENABLED: bool = True
    CONTEXT_STORE_MAX_SNAPSHOTS: int = 50
    CONTEXT_TTL_SECONDS: float = 300.0

    # Multimodal Fusion
    FUSION_ENGINE_ENABLED: bool = True
    FUSION_TEMPORAL_WINDOW_MS: float = 500.0
    FUSION_MIN_CONFIDENCE: float = 0.5

    # Task & Workflow Engine
    WORKFLOW_ENGINE_ENABLED: bool = True
    WORKFLOW_MAX_RETRIES: int = 2
    WORKFLOW_STEP_TIMEOUT_SEC: float = 5.0

    # Plugin & Skill Framework
    SKILL_FRAMEWORK_ENABLED: bool = True
    STRICT_SKILL_PERMISSIONS: bool = False

    # AI Reasoning & Planning Layer
    REASONING_ENABLED: bool = True
    AI_PLANNER_PROVIDER: str = "deterministic"
    QWEN_MODEL_NAME: str = "qwen2.5-1.5b-instruct"
    QWEN_MODEL_PATH: str = "backend/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
    LLM_PROVIDER: str = "mock"
    LLM_MODEL: str = "llama3:8b"
    LLM_API_URL: str = "http://localhost:11434"

    # Interaction Dataset Collection
    DATA_COLLECTION_ENABLED: bool = False
    DATASET_STORAGE_DIR: str = str(DATASET_DIR / "raw")
    TRAINING_DATASET_DIR: str = str(DATASET_DIR / "training_ready")

    # Runtime Platform & Production Hardening Layer
    RUNTIME_PLATFORM_ENABLED: bool = True
    HEALTH_CHECK_INTERVAL_SEC: float = 10.0
    METRICS_ENABLED: bool = True

    # Personal Productivity Tools Layer
    EMAIL_ACCOUNT: str | None = None
    EMAIL_SERVER: str | None = None
    CALENDAR_ACCOUNT: str | None = None
    GITHUB_API_TOKEN: str | None = None
    GITHUB_DEFAULT_REPO: str | None = None

    # Google OAuth 2.0 Integration
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"
    GOOGLE_CLIENT_SECRET_FILE: str = "backend/config/google_client_secret.json"

    # API Server
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000


settings = Settings()
