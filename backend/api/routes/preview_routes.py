"""FastAPI Router for Pre-Execution Workflow Preview & Risk Assessment."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.brain.dry_run_engine import DryRunEngine
from backend.brain.execution_planner import ExecutionPlanner
from backend.brain.risk_assessment import RiskAssessmentEngine
from backend.brain.workflow import TaskPlan, WorkflowStep

router = APIRouter(prefix="/workflow", tags=["workflow-preview"])


class WorkflowStepPayload(BaseModel):
    intent: str
    target: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class WorkflowPreviewRequest(BaseModel):
    name: str = "Preview Workflow"
    steps: list[WorkflowStepPayload]


@router.post("/preview")
def preview_workflow(req: WorkflowPreviewRequest):
    """Generate predictive ExecutionPlan, RiskReport, and DryRunResult without executing any actions."""
    wf_steps = [
        WorkflowStep(intent=s.intent, target=s.target, params=s.params)
        for s in req.steps
    ]
    plan = TaskPlan(name=req.name, steps=wf_steps)

    planner = ExecutionPlanner()
    risk_engine = RiskAssessmentEngine()
    dry_run_engine = DryRunEngine()

    exec_plan = planner.analyze_plan(plan)
    risk_report = risk_engine.evaluate_plan(plan)
    dry_run_res = dry_run_engine.simulate(plan)

    return {
        "execution_plan": {
            "plan_id": exec_plan.plan_id,
            "estimated_runtime_sec": exec_plan.estimated_runtime_sec,
            "required_applications": exec_plan.required_applications,
            "required_permissions": exec_plan.required_permissions,
            "expected_window_changes": exec_plan.expected_window_changes,
            "expected_desktop_state": exec_plan.expected_desktop_state,
            "potential_failures": exec_plan.potential_failures,
        },
        "risk_report": {
            "risk_level": risk_report.risk_level.value,
            "destructive_actions": risk_report.destructive_actions,
            "permission_requirements": risk_report.permission_requirements,
            "expected_side_effects": risk_report.expected_side_effects,
            "confirmation_required": risk_report.confirmation_required,
        },
        "dry_run_result": {
            "predicted_success_percent": dry_run_res.predicted_success_percent,
            "potential_failures": dry_run_res.potential_failures,
            "missing_skills": dry_run_res.missing_skills,
            "missing_apps": dry_run_res.missing_apps,
            "expected_runtime_sec": dry_run_res.expected_runtime_sec,
        },
    }
