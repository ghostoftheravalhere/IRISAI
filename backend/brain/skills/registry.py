"""Skill Registry and Validator service for dynamic capability discovery and execution."""

from __future__ import annotations

from threading import RLock
import time
from typing import Any

from backend.brain.skills.base import (
    Skill,
    SkillDescriptor,
    SkillExecutionContext,
    SkillResult,
)
from backend.brain.skills.events import (
    SkillExecutionCompletedEvent,
    SkillExecutionFailedEvent,
    SkillExecutionStartedEvent,
    SkillRegisteredEvent,
)
from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SkillValidator:
    """Validates permission requirements and capability matching before skill invocation."""

    @staticmethod
    def validate(
        skill: Skill,
        context: SkillExecutionContext,
        strict_permissions: bool = False,
    ) -> tuple[bool, str]:
        """Validate if user permissions and context satisfy Skill requirements."""
        desc = skill.descriptor
        if strict_permissions and desc.required_permissions:
            required_set = set(desc.required_permissions)
            user_set = set(context.user_permissions)
            if not required_set.issubset(user_set):
                missing = required_set - user_set
                return False, f"Permission denied for skill '{desc.skill_id}': missing permissions {sorted(list(missing))}"

        return skill.can_execute(context)


class SkillRegistry:
    """Central registry managing discovery, registration, validation, and execution of Skills."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        strict_permissions: bool = False,
        enabled: bool = True,
    ) -> None:
        self._event_bus = event_bus
        self._strict_permissions = strict_permissions
        self._enabled = enabled
        self._skills: dict[str, Skill] = {}
        self._capability_map: dict[str, str] = {}
        self._lock = RLock()

    @property
    def enabled(self) -> bool:
        """Return whether skill registry is active."""
        return self._enabled

    def register_skill(self, skill: Skill) -> None:
        """Register a Skill capability with the registry."""
        with self._lock:
            desc = skill.descriptor
            self._skills[desc.skill_id] = skill
            for cap in desc.capabilities:
                self._capability_map[cap] = desc.skill_id
            logger.info("Registered Skill: '%s' (v%s) with capabilities %s", desc.skill_id, desc.version, desc.capabilities)

            if self._event_bus:
                self._event_bus.publish(
                    SkillRegisteredEvent(
                        skill_id=desc.skill_id,
                        name=desc.name,
                        version=desc.version,
                    )
                )

    def get_skill(self, skill_id: str) -> Skill | None:
        """Retrieve a registered Skill by ID."""
        with self._lock:
            return self._skills.get(skill_id)

    def find_skill_for_intent(self, intent: str) -> Skill | None:
        """Find the registered Skill capable of executing the requested intent."""
        with self._lock:
            skill_id = self._capability_map.get(intent)
            if skill_id:
                return self._skills.get(skill_id)

            # Fallback scan capabilities
            for skill in self._skills.values():
                if intent in skill.descriptor.capabilities:
                    return skill
            return None

    def discover_skills(self) -> list[SkillDescriptor]:
        """Return descriptors for all registered Skills."""
        with self._lock:
            return [s.descriptor for s in self._skills.values()]

    def execute_skill(
        self,
        skill_id: str,
        context: SkillExecutionContext,
    ) -> SkillResult:
        """Validate and execute a target Skill by skill_id."""
        with self._lock:
            skill = self.get_skill(skill_id)
            if not skill:
                return SkillResult(
                    success=False,
                    message=f"Skill '{skill_id}' not found in registry.",
                    error_code="SKILL_NOT_FOUND",
                )

        return self._execute_validated_skill(skill, context)

    def execute_intent(
        self,
        intent: str,
        params: dict[str, Any] | None = None,
        context: SkillExecutionContext | None = None,
    ) -> SkillResult:
        """Find matching Skill for intent and execute it."""
        skill = self.find_skill_for_intent(intent)
        if not skill:
            return SkillResult(
                success=False,
                message=f"No Skill registered for intent '{intent}'.",
                error_code="NO_MATCHING_SKILL",
            )

        ctx = context or SkillExecutionContext(intent=intent, params=params or {})
        return self._execute_validated_skill(skill, ctx)

    def _execute_validated_skill(self, skill: Skill, context: SkillExecutionContext) -> SkillResult:
        """Internal helper validating permissions and executing skill with event tracking."""
        desc = skill.descriptor
        t0 = time.time()

        if self._event_bus:
            self._event_bus.publish(
                SkillExecutionStartedEvent(
                    skill_id=desc.skill_id,
                    intent=context.intent,
                    session_id=context.session_id,
                )
            )

        valid, reason = SkillValidator.validate(skill, context, self._strict_permissions)
        if not valid:
            logger.warning("Skill execution blocked for '%s': %s", desc.skill_id, reason)
            if self._event_bus:
                self._event_bus.publish(
                    SkillExecutionFailedEvent(
                        skill_id=desc.skill_id,
                        intent=context.intent,
                        reason=reason,
                    )
                )
            return SkillResult(
                success=False,
                message=reason,
                error_code="VALIDATION_FAILED",
            )

        try:
            result = skill.execute(context)
            duration_ms = (time.time() - t0) * 1000.0

            if self._event_bus:
                self._event_bus.publish(
                    SkillExecutionCompletedEvent(
                        skill_id=desc.skill_id,
                        intent=context.intent,
                        success=result.success,
                        execution_time_ms=duration_ms,
                    )
                )
            return result
        except Exception as exc:
            logger.exception("Exception executing Skill '%s'", desc.skill_id)
            if self._event_bus:
                self._event_bus.publish(
                    SkillExecutionFailedEvent(
                        skill_id=desc.skill_id,
                        intent=context.intent,
                        reason=str(exc),
                    )
                )
            return SkillResult(
                success=False,
                message=f"Skill execution failed: {exc}",
                error_code="EXECUTION_ERROR",
            )
