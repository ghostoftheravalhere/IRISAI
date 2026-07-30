"""Shared exception types for the IRIS AI V2 core layer."""

from __future__ import annotations


class IrisError(RuntimeError):
    """Base exception for IRIS AI domain failures."""


class PerceptionError(IrisError):
    """Raised when raw sensor capture or perception fails."""


class ActionError(IrisError):
    """Raised when action validation or execution fails."""
