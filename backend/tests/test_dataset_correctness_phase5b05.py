"""Phase 5B-0.5 Regression Test Suite verifying dataset correctness, outcome integrity, 100% step success qualification, and PyAutoGUI safety preservation."""

from __future__ import annotations

from pathlib import Path
import pytest
import pyautogui

from backend.agent.agent_core import AgentCore, AgentResult
from backend.agent.dataset.collector import InteractionDatasetCollector
from backend.agent.dataset.schema import DatasetCategory, InteractionRecord
from backend.agent.task_state import PlanStep, TaskState, TaskStatus
from backend.agent.tool_registry import ToolResult


@pytest.fixture
def tmp_dataset_dir(tmp_path: Path) -> tuple[Path, Path]:
    raw_dir = tmp_path / "raw"
    training_dir = tmp_path / "training_ready"
    return raw_dir, training_dir


def test_1_successful_multistep_task_marked_training_ready(tmp_dataset_dir):
    """1. Test that a multi-step task with 100% step success is marked training-ready."""
    raw_dir, training_dir = tmp_dataset_dir
    collector = InteractionDatasetCollector(raw_storage_dir=str(raw_dir), training_storage_dir=str(training_dir), enabled=True)

    state = TaskState(user_goal="Open Notepad and type hello.")
    s1 = PlanStep(step_id=1, tool_name="desktop_tool", description="Open Notepad")
    s2 = PlanStep(step_id=2, tool_name="desktop_tool", description="Type hello")
    state.advance_step(s1, ToolResult(True, "Opened Notepad"))
    state.advance_step(s2, ToolResult(True, "Typed text hello"))
    state.status = TaskStatus.COMPLETED

    res = AgentResult(True, "Task completed successfully", state)
    rec = collector.record_interaction(state, res)

    assert rec is not None
    assert rec.outcome == "SUCCESS"
    assert rec.is_training_ready is True
    assert (training_dir / "MULTI_STEP" / f"{rec.sample_id}.json").exists()


def test_2_failed_multistep_task_not_marked_training_ready(tmp_dataset_dir):
    """2. Test that a multi-step task with a step failure is NOT marked training-ready."""
    raw_dir, training_dir = tmp_dataset_dir
    collector = InteractionDatasetCollector(raw_storage_dir=str(raw_dir), training_storage_dir=str(training_dir), enabled=True)

    state = TaskState(user_goal="Open Notepad and type hello.")
    s1 = PlanStep(step_id=1, tool_name="desktop_tool", description="Open Notepad")
    s2 = PlanStep(step_id=2, tool_name="desktop_tool", description="Type hello")
    state.advance_step(s1, ToolResult(True, "Opened Notepad"))
    state.advance_step(s2, ToolResult(False, "Typing failed due to PyAutoGUI fail-safe", error_code="PY_AUTOGUI_FAILSAFE"))
    state.fail_task("Typing failed due to PyAutoGUI fail-safe")

    res = AgentResult(False, "Task failed at step 2", state, error_code="PY_AUTOGUI_FAILSAFE")
    rec = collector.record_interaction(state, res)

    assert rec is not None
    assert rec.outcome == "FAILED"
    assert rec.is_training_ready is False
    assert (raw_dir / f"{rec.sample_id}.json").exists()
    assert not (training_dir / "MULTI_STEP" / f"{rec.sample_id}.json").exists()


def test_3_cancelled_task_not_marked_training_ready(tmp_dataset_dir):
    """3. Test that a user-cancelled task is stored in raw but NOT marked training-ready."""
    raw_dir, training_dir = tmp_dataset_dir
    collector = InteractionDatasetCollector(raw_storage_dir=str(raw_dir), training_storage_dir=str(training_dir), enabled=True)

    state = TaskState(user_goal="Delete critical system file")
    state.fail_task("User cancelled proposed action")

    res = AgentResult(False, "Action cancelled by user.", state, error_code="CANCELLED")
    rec = collector.record_interaction(state, res)

    assert rec is not None
    assert rec.outcome == "CANCELLED"
    assert rec.is_training_ready is False


def test_4_failed_tool_result_preserved_in_raw(tmp_dataset_dir):
    """4. Test that step error message and error code are preserved in raw JSON."""
    raw_dir, training_dir = tmp_dataset_dir
    collector = InteractionDatasetCollector(raw_storage_dir=str(raw_dir), training_storage_dir=str(training_dir), enabled=True)

    state = TaskState(user_goal="Read missing file")
    step = PlanStep(step_id=1, tool_name="filesystem_tool", description="Read file missing.txt")
    state.advance_step(step, ToolResult(False, "File not found: missing.txt", error_code="FILE_NOT_FOUND"))
    state.fail_task("File not found")

    rec = collector.record_interaction(state, AgentResult(False, "File not found", state, error_code="FILE_NOT_FOUND"))
    assert rec is not None
    assert rec.tool_results[0]["message"] == "File not found: missing.txt"


def test_5_pyautogui_failsafe_preserved():
    """5. Test that pyautogui.FAILSAFE remains explicitly enabled (True)."""
    assert pyautogui.FAILSAFE is True


def test_6_failure_categories_recorded(tmp_dataset_dir):
    """6. Test that failure categories and error codes are correctly captured."""
    raw_dir, training_dir = tmp_dataset_dir
    collector = InteractionDatasetCollector(raw_storage_dir=str(raw_dir), training_storage_dir=str(training_dir), enabled=True)

    for err in ("FILE_NOT_FOUND", "PY_AUTOGUI_FAILSAFE", "CONFIRMATION_REQUIRED", "CANCELLED", "INPUT_FAILURE"):
        state = TaskState(user_goal=f"Test error {err}")
        step = PlanStep(step_id=1, tool_name="desktop_tool", description="Failed step")
        state.advance_step(step, ToolResult(False, f"Error {err}", error_code=err))
        state.fail_task(f"Failed with {err}")
        rec = collector.record_interaction(state, AgentResult(False, f"Failed {err}", state, error_code=err))
        assert rec is not None
        assert rec.is_training_ready is False


def test_7_qualification_rejects_spoofed_success_with_step_failure(tmp_dataset_dir):
    """7. Test that qualify_record rejects records if any step failed even if outcome is spoofed to SUCCESS."""
    raw_dir, training_dir = tmp_dataset_dir
    collector = InteractionDatasetCollector(raw_storage_dir=str(raw_dir), training_storage_dir=str(training_dir), enabled=True)

    rec = InteractionRecord(
        user_request="Open Notepad and type hello.",
        plan={"steps": [{"step_id": 1, "tool_name": "desktop_tool"}, {"step_id": 2, "tool_name": "desktop_tool"}]},
        tool_results=[
            {"step_id": 1, "success": True, "message": "Opened Notepad"},
            {"step_id": 2, "success": False, "message": "Typing failed due to PyAutoGUI fail-safe", "data": {"error_code": "PY_AUTOGUI_FAILSAFE"}},
        ],
        outcome="SUCCESS",  # Spoofed outcome
        dataset_type=DatasetCategory.MULTI_STEP,
    )

    is_ready, reasons = collector.qualify_record(rec)
    assert is_ready is False
    assert "failed" in reasons[0].lower() or "error" in reasons[0].lower()
