"""Risk Assessment Engine for Pre-Execution Safety Classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.brain.workflow import TaskPlan
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class RiskLevel(str, Enum):
    """Pre-execution safety risk levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskReport:
    """Safety evaluation report for a workflow plan."""

    risk_level: RiskLevel
    destructive_actions: list[str] = field(default_factory=list)
    permission_requirements: list[str] = field(default_factory=list)
    expected_side_effects: list[str] = field(default_factory=list)
    confirmation_required: bool = False


class RiskAssessmentEngine:
    """Evaluates potential risk levels and destructive side-effects of workflow steps."""

    def evaluate_plan(self, plan: TaskPlan) -> RiskReport:
        """Classify workflow plan risk level and side-effects."""
        destructive: list[str] = []
        perms: set[str] = set()
        side_effects: list[str] = []
        max_risk = RiskLevel.LOW

        for step in plan.steps:
            intent = step.intent.upper()
            target = (step.target or "").lower()

            if "FORMAT" in intent or "FORMAT_DRIVE" in intent or "wipe" in target:
                max_risk = RiskLevel.CRITICAL
                destructive.append(f"Format storage drive/volume ({target})")
                perms.add("CRITICAL_SYSTEM_DISK_ACCESS")
                side_effects.append("Permanent loss of unbacked data on target drive")

            elif "DELETE" in intent or "REMOVE" in intent or "clean" in target:
                if max_risk != RiskLevel.CRITICAL:
                    max_risk = RiskLevel.HIGH
                destructive.append(f"Delete file system resources ({step.target})")
                perms.add("WRITE_FILE_SYSTEM_PERMISSIONS")
                side_effects.append(f"Permanent deletion of target file '{step.target}'")

            elif "GIT_PUSH" in intent or "PUSH" in intent:
                if max_risk not in (RiskLevel.CRITICAL, RiskLevel.HIGH):
                    max_risk = RiskLevel.HIGH
                destructive.append("Push repository commits to remote origin")
                perms.add("NETWORK_REMOTE_WRITE_ACCESS")
                side_effects.append("Remote repository state mutation")

            elif "SHUTDOWN" in intent or "REBOOT" in intent:
                if max_risk not in (RiskLevel.CRITICAL, RiskLevel.HIGH):
                    max_risk = RiskLevel.MEDIUM
                destructive.append("Shutdown host operating system")
                side_effects.append("System reboot / session termination")

        confirm = max_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL) or len(destructive) > 1

        logger.info(
            "RiskAssessmentEngine evaluated plan '%s': risk=%s confirmation_required=%s",
            plan.name,
            max_risk.value,
            confirm,
        )

        return RiskReport(
            risk_level=max_risk,
            destructive_actions=destructive,
            permission_requirements=sorted(list(perms)),
            expected_side_effects=side_effects,
            confirmation_required=confirm,
        )
