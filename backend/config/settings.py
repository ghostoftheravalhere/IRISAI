"""Sprint 1 compatibility shim for the new core config settings path."""

# Keep legacy imports working while backend.core.config.settings becomes canonical.
from backend.core.config.settings import Settings, settings

__all__ = ["Settings", "settings"]
