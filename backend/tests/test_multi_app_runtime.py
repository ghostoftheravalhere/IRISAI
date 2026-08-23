"""Unit tests for Multi-Application Coordinator & Cross-Application Desktop Runtime Subsystem."""

from __future__ import annotations

from backend.brain.workflow import TaskPlan, WorkflowStep
from backend.runtime.clipboard_intelligence import ClipboardIntelligence
from backend.runtime.multi_application_coordinator import MultiApplicationCoordinator
from backend.runtime.workflow_optimizer import WorkflowOptimizer


def test_multi_application_coordinator_graphs():
    coord = MultiApplicationCoordinator()

    app_graph = coord.get_application_graph()
    assert len(app_graph) >= 2
    apps = [a["app_name"] for a in app_graph]
    assert "chrome" in apps
    assert "vscode" in apps

    windows = coord.get_window_relationships()
    assert len(windows) >= 2
    roles = [w["role"] for w in windows]
    assert "Dialog" in roles or "Terminal" in roles


def test_clipboard_intelligence_operations():
    clip = ClipboardIntelligence()

    assert clip.copy("import sys", source_app="vscode") is True
    assert clip.paste() == "import sys"

    assert clip.copy("def hello(): pass", source_app="chrome") is True
    assert clip.paste() == "def hello(): pass"

    assert clip.restore_previous() is True
    assert clip.paste() == "import sys"


def test_workflow_optimizer_redundant_launch_merging():
    optimizer = WorkflowOptimizer()

    plan = TaskPlan(
        name="Multi-App Plan",
        steps=[
            WorkflowStep(intent="OPEN_APPLICATION", target="chrome"),
            WorkflowStep(intent="OPEN_APPLICATION", target="chrome"),
            WorkflowStep(intent="SEARCH_BROWSER", target="chrome", params={"query": "pytest"}),
        ],
    )

    opt_plan = optimizer.optimize_plan(plan, active_apps=["chrome"])
    assert len(opt_plan.steps) == 1
    assert opt_plan.steps[0].intent == "SEARCH_BROWSER"
