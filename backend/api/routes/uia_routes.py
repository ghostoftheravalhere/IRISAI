"""FastAPI Router for Windows UI Automation Accessibility Dashboard Metrics."""

from __future__ import annotations

from fastapi import APIRouter

from backend.perception.ui_automation_engine import get_uia_metrics

router = APIRouter(prefix="/automation/uia", tags=["uia"])


@router.get("/metrics")
def get_ui_automation_metrics():
    """Get Windows UI Automation accessibility interaction metrics, fallback rates, and latencies."""
    return get_uia_metrics()
