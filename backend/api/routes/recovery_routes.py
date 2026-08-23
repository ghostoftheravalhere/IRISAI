"""FastAPI Router for Self-Healing Adaptive Recovery Metrics and Simulation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.agent.adaptive_recovery import AdaptiveRecoveryEngine, get_recovery_metrics
from backend.brain.workflow import TaskPlan, WorkflowStep

router = APIRouter(prefix="/recovery", tags=["recovery"])


class SimulationRequest(BaseModel):
    failed_intent: str = "CLICK_VISUAL_TEXT"
    failed_target: str = "Settings"
    step_index: int = 0


@router.get("/metrics")
def get_adaptive_recovery_metrics():
    """Get self-healing adaptive recovery metrics, UI changes detected, and replan counts."""
    return get_recovery_metrics()


@router.post("/simulate")
def simulate_recovery(req: SimulationRequest):
    """Simulate adaptive self-healing recovery for a failed workflow step."""
    step = WorkflowStep(intent=req.failed_intent, target=req.failed_target)
    plan = TaskPlan(name="Simulation Plan", steps=[step])

    engine = AdaptiveRecoveryEngine()
    # Mock workflow engine object with replace_step interface
    class _DummyWorkflowEngine:
        def replace_step(self, p, idx, ns):
            p.steps[idx] = ns
            return True

    res = engine.attempt_recovery(step, req.step_index, plan, _DummyWorkflowEngine())

    return {
        "success": res.success,
        "confidence": res.confidence,
        "reason": res.reason,
        "fallback_used": res.fallback_used,
        "attempts": res.attempts,
        "replanned_target": res.replanned_step.target if res.replanned_step else None,
    }
