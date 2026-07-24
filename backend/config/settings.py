"""
Application Settings
Loaded from .env file via pydantic-settings.
Import: from backend.config.settings import settings
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

    # Eye Tracking
    WEBCAM_INDEX: int = 0
    GAZE_SMOOTHING: float = 0.5

    # Voice
    WHISPER_MODEL: str = "base"
    MIC_SAMPLE_RATE: int = 16000

    # API Server
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000


settings = Settings()
