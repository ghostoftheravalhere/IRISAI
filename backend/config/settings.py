"""Sprint 1 compatibility shim for the new core config settings path."""

# Keep legacy imports working while backend.core.config.settings becomes canonical.
from backend.core.config.settings import (
    APP_DATA_DIR,
    CALIBRATION_DIR,
    DATASET_DIR,
    LOGS_DIR,
    RECORDINGS_DIR,
    Settings,
    get_app_data_dir,
    settings,
)

__all__ = [
    "Settings",
    "settings",
    "get_app_data_dir",
    "APP_DATA_DIR",
    "DATASET_DIR",
    "LOGS_DIR",
    "RECORDINGS_DIR",
    "CALIBRATION_DIR",
]
