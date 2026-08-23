"""FastAPI Router for Self-Verifying Automation Dashboard Metrics."""

from __future__ import annotations

from fastapi import APIRouter

from backend.agent.verification_engine import get_verification_metrics

router = APIRouter(prefix="/automation/verification", tags=["verification"])


@router.get("/metrics")
def get_action_verification_metrics():
    """Get self-verifying action automation metrics, success rates, and latency statistics."""
    return get_verification_metrics()
