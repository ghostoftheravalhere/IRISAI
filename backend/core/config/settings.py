"""
Application Settings
Loaded from .env file via pydantic-settings.
Import: from backend.core.config.settings import settings
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_ENV: str = "development"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./iris_ai.db"

    # Gemini AI
    GEMINI_API_KEY: str = ""

    # Eye Tracking / accessibility interaction
    WEBCAM_INDEX: int = 0
    GAZE_SMOOTHING: float = 0.28
    EAR_CLOSE_THRESHOLD: float = 0.21
    EAR_OPEN_THRESHOLD: float = 0.26
    INTENTIONAL_BLINK_MIN_MS: float = 500.0
    INTENTIONAL_BLINK_MAX_MS: float = 1200.0
    DOUBLE_LONG_BLINK_WINDOW_MS: float = 400.0
    CURSOR_SENSITIVITY: float = 0.92
    CURSOR_SMOOTHING: float = 0.12
    CURSOR_DEAD_ZONE_PX: float = 28.0
    CURSOR_MIN_MOVE_PX: float = 2.5
    CURSOR_MAX_STEP_PX: float = 48.0
    TRACKING_CONFIDENCE_THRESHOLD: float = 0.45
    CALIBRATION_QUALITY_THRESHOLD: float = 0.45
    CALIBRATION_RMSE_SCALE: float = 5.0
    CALIBRATION_GOOD_SCORE_THRESHOLD: float = 0.58
    OVERLAY_MODE: str = "normal"

    # Voice
    WHISPER_MODEL: str = "base"
    VOICE_MODEL_PATH: str | None = None
    MIC_SAMPLE_RATE: int = 16000
    VOICE_LISTEN_MODE: str = "continuous"
    VOICE_OUTPUT_ENABLED: bool = False  # V2.4 Submission Stability Mode (Voice Input Active, Spoken Output Disabled)
    ENABLE_AGC: bool = True
    AUDIO_PREPROCESSOR_ENABLED: bool = True
    AGC_ENABLED: bool = True
    AGC_TARGET_RMS: float = 0.04
    AGC_MIN_GAIN: float = 1.0
    AGC_MAX_GAIN: float = 40.0
    PEAK_LIMITER_THRESHOLD: float = 1.0

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
    DATASET_STORAGE_DIR: str = "backend/dataset/raw"
    TRAINING_DATASET_DIR: str = "backend/dataset/training_ready"

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
