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
    MIC_SAMPLE_RATE: int = 16000
    VOICE_LISTEN_MODE: str = "continuous"

    # API Server
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000


settings = Settings()
