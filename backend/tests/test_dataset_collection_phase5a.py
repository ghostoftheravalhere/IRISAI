"""Phase 5A Integration Test Suite verifying IRIS Interaction Dataset Collection, Secret Redaction, Qualification Rules, and Human Correction Capture."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from backend.agent.agent_core import AgentCore, AgentResult
from backend.agent.dataset.collector import InteractionDatasetCollector
from backend.agent.dataset.redactor import SecretRedactor
from backend.agent.dataset.schema import DatasetCategory, EvaluationSplit, InteractionRecord
from backend.agent.task_state import PlanStep, TaskState, TaskStatus
from backend.agent.tool_registry import ToolResult


@pytest.fixture
def tmp_dataset_dir(tmp_path: Path) -> tuple[Path, Path]:
    raw_dir = tmp_path / "raw"
    training_dir = tmp_path / "training_ready"
    return raw_dir, training_dir


def test_1_record_creation():
    """1. Test InteractionRecord creation and schema defaults."""
    record = InteractionRecord(
        user_request="Find my project report.",
        dataset_type=DatasetCategory.PLANNING,
    )
    assert record.user_request == "Find my project report."
    assert record.sample_id != ""
    assert record.dataset_type == DatasetCategory.PLANNING
    assert record.split == EvaluationSplit.TRAIN


def test_2_schema_validation_and_serialization():
    """2. Test schema to_dict and from_dict roundtrip serialization."""
    record = InteractionRecord(
        user_request="Check repository status.",
        dataset_type=DatasetCategory.TOOL_SELECTION,
        split=EvaluationSplit.VALIDATION,
    )
    data = record.to_dict()
    assert data["dataset_type"] == "TOOL_SELECTION"
    assert data["split"] == "val"

    reconstructed = InteractionRecord.from_dict(data)
    assert reconstructed.user_request == record.user_request
    assert reconstructed.dataset_type == DatasetCategory.TOOL_SELECTION
    assert reconstructed.split == EvaluationSplit.VALIDATION


def test_3_secret_redaction():
    """3. Test automated secret redaction for API keys, passwords, and tokens."""
    sensitive_text = "Connect with api_key: sk-1234567890abcdef12345678 and Bearer token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.secret"
    clean_text = SecretRedactor.redact_text(sensitive_text)
    assert "sk-1234567890abcdef12345678" not in clean_text
    assert "[REDACTED_SECRET]" in clean_text

    sanitized_dict = SecretRedactor.sanitize({"user": "admin", "password": "SuperSecretPassword123"})
    assert sanitized_dict["password"] == "[REDACTED_SECRET]"


def test_4_disabled_collection_switch(tmp_dataset_dir):
    """4. Test that DATA_COLLECTION_ENABLED=False produces zero record disk writes."""
    raw_dir, training_dir = tmp_dataset_dir
    collector = InteractionDatasetCollector(raw_storage_dir=str(raw_dir), training_storage_dir=str(training_dir), enabled=False)

    assert not collector.enabled
    state = TaskState(user_goal="Open Chrome.")
    res = collector.record_interaction(state, AgentResult(True, "Opened", state))
    assert res is None
    assert len(list(raw_dir.glob("*.json"))) == 0


def test_5_successful_task_record(tmp_dataset_dir):
    """5. Test recording a successful agent task interaction."""
    raw_dir, training_dir = tmp_dataset_dir
    collector = InteractionDatasetCollector(raw_storage_dir=str(raw_dir), training_storage_dir=str(training_dir), enabled=True)

    state = TaskState(user_goal="Open Chrome.")
    step = PlanStep(step_id=1, tool_name="desktop_tool", description="Open Chrome browser", params={"action": "open_application", "target": "chrome"})
    state.advance_step(step, ToolResult(True, "Chrome opened"))

    res = AgentResult(True, "Completed request.", state)
    rec = collector.record_interaction(state, res)

    assert rec is not None
    assert rec.is_training_ready
    assert (raw_dir / f"{rec.sample_id}.json").exists()


def test_6_failed_task_record(tmp_dataset_dir):
    """6. Test recording a failed task interaction with failure outcome."""
    raw_dir, training_dir = tmp_dataset_dir
    collector = InteractionDatasetCollector(raw_storage_dir=str(raw_dir), training_storage_dir=str(training_dir), enabled=True)

    state = TaskState(user_goal="Read missing file.")
    state.fail_task("File not found")
    res = AgentResult(False, "Failed to read file", state, error_code="FILE_NOT_FOUND")

    rec = collector.record_interaction(state, res)
    assert rec is not None
    assert rec.outcome == "FAILED"


def test_7_correction_record(tmp_dataset_dir):
    """7. Test capturing human correction events."""
    raw_dir, training_dir = tmp_dataset_dir
    collector = InteractionDatasetCollector(raw_storage_dir=str(raw_dir), training_storage_dir=str(training_dir), enabled=True)

    rec = collector.record_user_correction(
        original_goal="Open Calculator",
        corrected_goal="Open Notepad",
        original_plan={"goal": "Open Calculator"},
        corrected_plan={"goal": "Open Notepad"},
        reason="User corrected application choice",
    )
    assert rec is not None
    assert rec.dataset_type == DatasetCategory.CORRECTION
    assert rec.user_correction["corrected_goal"] == "Open Notepad"


def test_8_clarification_record(tmp_dataset_dir):
    """8. Test capturing candidate ambiguity resolution under CLARIFICATION category."""
    raw_dir, training_dir = tmp_dataset_dir
    collector = InteractionDatasetCollector(raw_storage_dir=str(raw_dir), training_storage_dir=str(training_dir), enabled=True)

    state = TaskState(user_goal="Find report")
    state.candidates = [{"index": 1, "name": "report1.md"}, {"index": 2, "name": "report2.md"}]
    res = AgentResult(True, "Multiple reports found", state)

    rec = collector.record_interaction(state, res)
    assert rec is not None
    assert rec.dataset_type == DatasetCategory.CLARIFICATION


def test_9_multistep_task_record(tmp_dataset_dir):
    """9. Test capturing multi-step task interaction under MULTI_STEP category."""
    raw_dir, training_dir = tmp_dataset_dir
    collector = InteractionDatasetCollector(raw_storage_dir=str(raw_dir), training_storage_dir=str(training_dir), enabled=True)

    state = TaskState(user_goal="Open Notepad and type hello.")
    s1 = PlanStep(step_id=1, tool_name="desktop_tool", description="Open Notepad")
    s2 = PlanStep(step_id=2, tool_name="desktop_tool", description="Type hello")
    state.advance_step(s1, ToolResult(True, "Opened"))
    state.advance_step(s2, ToolResult(True, "Typed"))

    rec = collector.record_interaction(state, AgentResult(True, "Finished", state))
    assert rec is not None
    assert rec.dataset_type == DatasetCategory.MULTI_STEP


def test_10_training_ready_qualification_rules(tmp_dataset_dir):
    """10. Test qualification engine rejecting secret leaks or invalid requests."""
    raw_dir, training_dir = tmp_dataset_dir
    collector = InteractionDatasetCollector(raw_storage_dir=str(raw_dir), training_storage_dir=str(training_dir), enabled=True)

    # Empty request should fail qualification
    invalid_rec = InteractionRecord(user_request="  ", dataset_type=DatasetCategory.PLANNING)
    is_ready, reasons = collector.qualify_record(invalid_rec)
    assert not is_ready
    assert "empty" in reasons[0].lower()
