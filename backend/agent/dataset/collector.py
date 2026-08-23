"""InteractionDatasetCollector orchestrating raw record storage, secret sanitization, training-ready qualification, and category partitioning."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from backend.agent.dataset.redactor import SecretRedactor
from backend.agent.dataset.schema import DatasetCategory, EvaluationSplit, InteractionRecord
from backend.agent.task_state import TaskState
from backend.config.settings import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class InteractionDatasetCollector:
    """Collects, redacts, qualifies, and partitions IRIS interaction data for offline model fine-tuning."""

    def __init__(
        self,
        raw_storage_dir: str | None = None,
        training_storage_dir: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        self._enabled = enabled if enabled is not None else getattr(settings, "DATA_COLLECTION_ENABLED", False)
        self._raw_dir = Path(raw_storage_dir or getattr(settings, "DATASET_STORAGE_DIR", "backend/dataset/raw"))
        self._training_dir = Path(training_storage_dir or getattr(settings, "TRAINING_DATASET_DIR", "backend/dataset/training_ready"))

        if self._enabled:
            self._raw_dir.mkdir(parents=True, exist_ok=True)
            self._training_dir.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _determine_category(self, task_state: TaskState, agent_result: AgentResult) -> DatasetCategory:
        """Categorize interaction based on task characteristics."""
        if task_state.user_correction:
            return DatasetCategory.CORRECTION
        if task_state.pending_confirmation:
            return DatasetCategory.SAFETY
        if task_state.candidates:
            return DatasetCategory.CLARIFICATION
        if task_state.history and len(task_state.history) > 1:
            return DatasetCategory.MULTI_STEP
        if task_state.history and len(task_state.history) == 1:
            step, _ = task_state.history[0]
            if step.tool_name in ("git_tool", "filesystem_tool", "web_search_tool"):
                return DatasetCategory.TOOL_SELECTION
        return DatasetCategory.PLANNING

    def _assign_split(self, session_id: str) -> EvaluationSplit:
        """Assign evaluation split based on session_id hash (70% train, 15% val, 15% test)."""
        val_hash = int(hashlib.md5(session_id.encode("utf-8")).hexdigest(), 16) % 100
        if val_hash < 70:
            return EvaluationSplit.TRAIN
        if val_hash < 85:
            return EvaluationSplit.VALIDATION
        return EvaluationSplit.TEST

    def qualify_record(self, record: InteractionRecord) -> tuple[bool, list[str]]:
        """Evaluate qualification criteria for training readiness."""
        reasons: list[str] = []

        if not record.user_request or len(record.user_request.strip()) < 3:
            return False, ["User request is empty or too short"]

        if not record.plan or "steps" not in record.plan:
            return False, ["Missing valid plan structure"]

        # Human correction records carry explicitly corrected plans
        if record.dataset_type == DatasetCategory.CORRECTION:
            reasons.append("Human correction record verified")
            return True, reasons

        # Training-ready records MUST have a SUCCESS outcome
        if record.outcome != "SUCCESS":
            return False, [f"Record outcome is '{record.outcome}', only SUCCESS records are training-ready"]

        # All tool step results MUST have executed successfully
        for step_res in record.tool_results:
            res_msg = str(step_res.get("message") or "").lower()
            res_data = step_res.get("data") or {}
            if "failed" in res_msg or "error" in res_msg or res_data.get("error_code"):
                return False, [f"Tool step execution failed or reported error: {res_msg}"]

        # Secret check
        if SecretRedactor.contains_unredacted_secret(record.to_dict()):
            return False, ["Unredacted sensitive credentials present"]

        # Ambiguity check
        if record.dataset_type == DatasetCategory.CLARIFICATION and record.user_correction is None and not record.context.get("last_resolved_target"):
            return False, ["Unresolved target ambiguity remains"]

        reasons.append("Valid request and plan schema")
        reasons.append("100% step execution success verified")
        reasons.append("Zero secret leaks detected")

        return True, reasons

    def record_interaction(
        self,
        task_state: TaskState,
        agent_result: AgentResult,
        user_correction: dict[str, Any] | None = None,
    ) -> InteractionRecord | None:
        """Capture an AgentCore interaction into sanitized raw and qualified training datasets."""
        if not self._enabled:
            return None

        try:
            category = self._determine_category(task_state, agent_result)
            split = self._assign_split(task_state.task_id)

            # Sanitize request and context
            clean_request = SecretRedactor.redact_text(task_state.user_goal)
            clean_context = SecretRedactor.sanitize({
                "active_app": task_state.active_application,
                "active_window": task_state.active_window,
                "last_resolved_target": task_state.last_resolved_target,
                "candidates": task_state.candidates,
            })

            # Format steps and results
            tool_calls = []
            tool_results = []
            steps_data = []

            for step, res in task_state.history:
                clean_params = SecretRedactor.sanitize(step.params)
                tool_calls.append({"step_id": step.step_id, "tool_name": step.tool_name, "params": clean_params})
                clean_res_msg = SecretRedactor.redact_text(getattr(res, "message", str(res)))
                clean_res_data = SecretRedactor.sanitize(getattr(res, "data", {})) if hasattr(res, "data") else {}
                tool_results.append({"step_id": step.step_id, "message": clean_res_msg, "data": clean_res_data})
                steps_data.append({"step_id": step.step_id, "tool_name": step.tool_name, "description": step.description, "params": clean_params})

            plan_dict = {"goal": clean_request, "steps": steps_data}
            clean_response = SecretRedactor.redact_text(agent_result.response)

            outcome = "SUCCESS" if agent_result.success else ("CANCELLED" if agent_result.error_code == "CANCELLED" else "FAILED")
            safety_state = "CONFIRMATION_REQUIRED" if agent_result.error_code == "CONFIRMATION_REQUIRED" else "SAFE"

            record = InteractionRecord(
                session_id=task_state.task_id,
                user_request=clean_request,
                context=clean_context,
                provider=task_state.current_plan.goal if task_state.current_plan else "deterministic",
                plan=plan_dict,
                tool_calls=tool_calls,
                tool_results=tool_results,
                final_response=clean_response,
                outcome=outcome,
                user_correction=user_correction,
                safety_state=safety_state,
                dataset_type=category,
                split=split,
            )

            # Evaluate qualification for training readiness
            is_ready, reasons = self.qualify_record(record)
            record.is_training_ready = is_ready
            record.qualification_reasons = reasons

            # Save raw record
            raw_path = self._raw_dir / f"{record.sample_id}.json"
            raw_path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")

            # Save training-ready record if qualified
            if is_ready:
                cat_dir = self._training_dir / record.dataset_type.value
                cat_dir.mkdir(parents=True, exist_ok=True)
                ready_path = cat_dir / f"{record.sample_id}.json"
                ready_path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")

            logger.info("Recorded dataset sample %s (category=%s, ready=%s)", record.sample_id, category.value, is_ready)
            return record

        except Exception as exc:
            logger.warning("Failed to record interaction dataset sample: %s", exc)
            return None

    def record_user_correction(
        self,
        original_goal: str,
        corrected_goal: str,
        original_plan: dict[str, Any],
        corrected_plan: dict[str, Any],
        reason: str = "User corrected interpretation",
    ) -> InteractionRecord | None:
        """Capture human correction event for dataset fine-tuning."""
        if not self._enabled:
            return None

        correction_data = {
            "original_goal": SecretRedactor.redact_text(original_goal),
            "corrected_goal": SecretRedactor.redact_text(corrected_goal),
            "original_plan": SecretRedactor.sanitize(original_plan),
            "corrected_plan": SecretRedactor.sanitize(corrected_plan),
            "reason": SecretRedactor.redact_text(reason),
        }

        record = InteractionRecord(
            user_request=correction_data["corrected_goal"],
            context={"correction_reason": reason},
            plan=correction_data["corrected_plan"],
            outcome="SUCCESS",
            user_correction=correction_data,
            dataset_type=DatasetCategory.CORRECTION,
            is_training_ready=True,
            qualification_reasons=["User human correction record"],
        )

        cat_dir = self._training_dir / DatasetCategory.CORRECTION.value
        cat_dir.mkdir(parents=True, exist_ok=True)
        ready_path = cat_dir / f"{record.sample_id}.json"
        ready_path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")

        return record
