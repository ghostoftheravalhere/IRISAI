"""Adaptive Self-Healing Recovery Engine for UI Change Mitigation."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any

from backend.brain.workflow import TaskPlan, WorkflowEngine, WorkflowStep
from backend.memory.memory_manager import MemoryManager
from backend.perception.ui_automation_engine import UIAutomationEngine
from backend.perception.ui_change_detector import UIChangeDetector
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Telemetry Metrics Collection
_RECOVERY_METRICS = {
    "total_recoveries": 0,
    "successful_recoveries": 0,
    "failed_recoveries": 0,
    "total_recovery_time_sec": 0.0,
    "ui_changes_detected": 0,
    "automatic_replans": 0,
    "human_escalations": 0,
    "recovery_history": [],
}


def get_recovery_metrics() -> dict[str, Any]:
    """Return runtime metrics for self-healing recovery dashboard."""
    total = _RECOVERY_METRICS["total_recoveries"]
    succ = _RECOVERY_METRICS["successful_recoveries"]
    succ_rate = (succ / total * 100.0) if total > 0 else 100.0
    avg_time = (_RECOVERY_METRICS["total_recovery_time_sec"] / total * 1000.0) if total > 0 else 0.0

    return {
        "total_recoveries": total,
        "successful_recoveries": succ,
        "failed_recoveries": _RECOVERY_METRICS["failed_recoveries"],
        "recovery_success_percent": round(succ_rate, 2),
        "average_recovery_time_ms": round(avg_time, 2),
        "ui_changes_detected": _RECOVERY_METRICS["ui_changes_detected"],
        "automatic_replans": _RECOVERY_METRICS["automatic_replans"],
        "human_escalations": _RECOVERY_METRICS["human_escalations"],
        "recovery_history": list(_RECOVERY_METRICS["recovery_history"][-20:]),
    }


@dataclass
class AdaptiveRecoveryResult:
    """Outcome of an adaptive self-healing recovery attempt."""

    success: bool
    confidence: float = 1.0
    reason: str = "Recovery successful"
    fallback_used: str = "Semantic Alias Match"
    attempts: int = 1
    replanned_step: WorkflowStep | None = None


class AdaptiveRecoveryEngine:
    """Engine responsible for self-healing recovery from UI changes, control moves, or popups."""

    # Semantic UI Control Synonym Map
    CONTROL_SYNONYMS = {
        "settings": ["settings", "preferences", "options", "config", "gear"],
        "save": ["save", "save file", "save as", "submit", "confirm"],
        "chrome": ["chrome", "browser", "google chrome"],
        "close": ["close", "cancel", "dismiss"],
    }

    def __init__(
        self,
        uia_engine: UIAutomationEngine | None = None,
        memory_manager: MemoryManager | None = None,
    ) -> None:
        self._uia_engine = uia_engine or UIAutomationEngine()
        self._memory_manager = memory_manager
        self._change_detector = UIChangeDetector()

    def attempt_recovery(
        self,
        failed_step: WorkflowStep,
        step_index: int,
        plan: TaskPlan,
        workflow_engine: WorkflowEngine,
    ) -> AdaptiveRecoveryResult:
        """Execute self-healing recovery for a failed workflow step."""
        start_time = time.monotonic()
        _RECOVERY_METRICS["total_recoveries"] += 1

        target = (failed_step.target or failed_step.intent).lower()
        synonyms = self.CONTROL_SYNONYMS.get(target, [target])

        # Step 1: Check MemoryManager for learned UI control aliases
        learned_alias = None
        if self._memory_manager:
            mem = self._memory_manager.recall(f"ui_alias_{target}")
            if mem:
                learned_alias = mem

        # Step 2: Inspect accessibility tree for semantic alternative control
        found_alias = learned_alias
        if not found_alias:
            elements = self._uia_engine.find_all()
            for syn in synonyms:
                for el in elements:
                    if syn in el.name.lower():
                        found_alias = el.name
                        break
                if found_alias:
                    break

        if found_alias:
            # Step 3: Partial Workflow Replanning using replace_step
            new_step = WorkflowStep(
                intent=failed_step.intent,
                target=found_alias,
                params=failed_step.params,
            )
            workflow_engine.replace_step(plan, step_index, new_step)

            # Save learned strategy into MemoryManager
            if self._memory_manager and not learned_alias:
                self._memory_manager.store(f"ui_alias_{target}", found_alias, metadata={"type": "learned_ui_alias"})

            elapsed = time.monotonic() - start_time
            _RECOVERY_METRICS["successful_recoveries"] += 1
            _RECOVERY_METRICS["total_recovery_time_sec"] += elapsed
            _RECOVERY_METRICS["automatic_replans"] += 1
            _RECOVERY_METRICS["ui_changes_detected"] += 1

            res = AdaptiveRecoveryResult(
                success=True,
                confidence=0.95,
                reason=f"Recovered '{target}' via semantic alternative control '{found_alias}'",
                fallback_used="Semantic UIA Search",
                attempts=1,
                replanned_step=new_step,
            )

            logger.info("AdaptiveRecoveryEngine successfully recovered step %d (%s -> %s)", step_index, target, found_alias)
            return res

        # Fallback: Escalate if recovery fails
        elapsed = time.monotonic() - start_time
        _RECOVERY_METRICS["failed_recoveries"] += 1
        _RECOVERY_METRICS["human_escalations"] += 1

        logger.warning("AdaptiveRecoveryEngine failed to find alternative control for '%s'", target)
        return AdaptiveRecoveryResult(
            success=False,
            confidence=0.0,
            reason=f"No semantic alternative control found for '{target}'",
            fallback_used="None",
            attempts=1,
        )
