"""Configuration Validator service for pre-boot environment settings validation."""

from __future__ import annotations

from backend.core.config.settings import Settings
from backend.core.events.bus import EventBus
from backend.platform.runtime_events import ConfigurationValidationErrorEvent
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ConfigurationValidator:
    """Validates application environment settings before service initialization."""

    @staticmethod
    def validate_settings(
        app_settings: Settings,
        event_bus: EventBus | None = None,
    ) -> tuple[bool, list[str]]:
        """Validate critical configuration parameters."""
        errors: list[str] = []

        # Audio settings check
        if app_settings.MIC_SAMPLE_RATE <= 0:
            errors.append(f"MIC_SAMPLE_RATE must be > 0 (got {app_settings.MIC_SAMPLE_RATE})")

        # API Server check
        if not (1024 <= app_settings.API_PORT <= 65535):
            errors.append(f"API_PORT must be between 1024 and 65535 (got {app_settings.API_PORT})")

        # LLM settings check
        if app_settings.LLM_PROVIDER == "ollama":
            url = app_settings.LLM_API_URL or ""
            if not (url.startswith("http://") or url.startswith("https://")):
                errors.append(f"LLM_API_URL must start with http:// or https:// (got '{url}')")

        if errors:
            for err in errors:
                logger.error("Configuration validation error: %s", err)
                if event_bus:
                    event_bus.publish(
                        ConfigurationValidationErrorEvent(
                            setting_key="settings",
                            error_message=err,
                        )
                    )
            return False, errors

        return True, []
