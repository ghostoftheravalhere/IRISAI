"""Unit tests for Deterministic Execution Intelligence & Risk Pre-Analysis Subsystem."""

from __future__ import annotations

from backend.brain.dry_run_engine import DryRunEngine
from backend.brain.execution_planner import ExecutionPlanner
from backend.brain.risk_assessment import RiskAssessmentEngine, RiskLevel
from backend.brain.workflow import TaskPlan, WorkflowStep
from backend.dialogue.dialogue_manager import DialogueManager


def test_execution_planner_analysis():
    planner = ExecutionPlanner()
    plan = TaskPlan(
        name="Study Plan",
        steps=[
            WorkflowStep(intent="OPEN_APPLICATION", target="chrome"),
            WorkflowStep(intent="SEARCH_BROWSER", target="chrome", params={"query": "AI research"}),
        ],
    )

    exec_plan = planner.analyze_plan(plan)
    assert exec_plan.estimated_runtime_sec > 0.0
    assert "chrome" in exec_plan.required_applications
    assert len(exec_plan.expected_window_changes) >= 2


def test_risk_assessment_engine_levels():
    risk_engine = RiskAssessmentEngine()

    plan_low = TaskPlan(steps=[WorkflowStep(intent="OPEN_APPLICATION", target="chrome")])
    rep_low = risk_engine.evaluate_plan(plan_low)
    assert rep_low.risk_level == RiskLevel.LOW
    assert rep_low.confirmation_required is False

    plan_high = TaskPlan(steps=[WorkflowStep(intent="DELETE_FILE", target="C:/Downloads/temp.zip")])
    rep_high = risk_engine.evaluate_plan(plan_high)
    assert rep_high.risk_level == RiskLevel.HIGH
    assert rep_high.confirmation_required is True

    plan_critical = TaskPlan(steps=[WorkflowStep(intent="FORMAT_DRIVE", target="D:")])
    rep_critical = risk_engine.evaluate_plan(plan_critical)
    assert rep_critical.risk_level == RiskLevel.CRITICAL
    assert rep_critical.confirmation_required is True


def test_dry_run_engine_simulation():
    dry_run = DryRunEngine()
    plan = TaskPlan(steps=[WorkflowStep(intent="OPEN_APPLICATION", target="chrome")])

    res = dry_run.simulate(plan)
    assert res.predicted_success_percent == 100.0
    assert len(res.potential_failures) == 0

    plan_fail = TaskPlan(steps=[WorkflowStep(intent="UNKNOWN_SKILL_INTENT")])
    res_fail = dry_run.simulate(plan_fail)
    assert res_fail.predicted_success_percent < 100.0
    assert len(res_fail.missing_skills) > 0


def test_dialogue_manager_confirmation_policy():
    dm = DialogueManager()
    risk_engine = RiskAssessmentEngine()

    plan_high = TaskPlan(steps=[WorkflowStep(intent="DELETE_FILE", target="data.db")])
    report = risk_engine.evaluate_plan(plan_high)

    req_confirm, msg = dm.check_confirmation_required(report)
    assert req_confirm is True
    assert "HIGH" in msg
