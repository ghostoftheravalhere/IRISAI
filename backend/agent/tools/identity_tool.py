"""IdentityTool providing local, privacy-first person identity querying and management."""

from __future__ import annotations

from typing import Any

from backend.agent.policy_engine import PermissionLevel
from backend.agent.task_state import TaskState
from backend.agent.tool_registry import ToolDescriptor, ToolResult
from backend.brain.world_model import world_model
from backend.perception.identity_manager import EnrollmentStatus, identity_manager
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class IdentityTool:
    """Read-Only & Confirmed Local Identity Management Tool for IRIS AI V4."""

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            tool_id="identity_tool",
            name="identity_tool",
            description="Queries local person identity, remembers named people with confirmation, and forgets saved identities safely.",
            permission_level=PermissionLevel.SAFE,
            input_schema={
                "action": "query_current_person | remember_person | reject_person | forget_person | forget_all",
                "name": "Name of person (e.g. 'Rahul')",
                "confirmed": "bool flag for destructive operations like forget_all",
            },
            output_schema={"success": "bool", "message": "str", "data": "dict"},
        )

    def is_configured(self) -> bool:
        return True

    def execute(self, params: dict[str, Any], task_state: TaskState | None = None) -> ToolResult:
        action = str(params.get("action") or "query_current_person").lower()
        name = str(params.get("name") or "").strip()
        confirmed = bool(params.get("confirmed") or False)

        try:
            if action == "greet":
                snap = world_model.snapshot()
                p_name = snap.person.name if (snap.person and snap.person.status == EnrollmentStatus.KNOWN.value and snap.person.name) else None
                msg = f"Hello {p_name}! How can I help you today?" if p_name else "Hello! How can I help you today?"
                return ToolResult(
                    success=True,
                    message=msg,
                    data={"greeting": msg, "person_name": p_name},
                )

            if action == "query_current_person":
                snap = world_model.snapshot()
                p_state = snap.person
                if p_state.status == EnrollmentStatus.KNOWN.value and p_state.name:
                    return ToolResult(
                        success=True,
                        message=f"That's {p_state.name}.",
                        data={"person_name": p_state.name, "status": p_state.status, "confidence": p_state.confidence},
                    )
                elif p_state.status == EnrollmentStatus.PENDING_IDENTIFICATION.value:
                    return ToolResult(
                        success=True,
                        message="I detect someone, but confidence is low. I don't recognize this person.",
                        data={"status": p_state.status, "confidence": p_state.confidence},
                    )
                else:
                    return ToolResult(
                        success=True,
                        message="I don't recognize this person. Who is this?",
                        data={"status": EnrollmentStatus.UNKNOWN.value},
                    )

            if action == "remember_person":
                if not name:
                    return ToolResult(success=False, message="Please specify the name of the person to remember.", error_code="MISSING_NAME")

                if not confirmed:
                    logger.info("Requesting confirmation before enrolling person '%s'", name)
                    return ToolResult(
                        success=False,
                        message=f"I heard {name}. Would you like me to remember {name}?",
                        data={"requires_confirmation": True, "tool_name": "identity_tool", "action": "remember_person", "name": name},
                        error_code="CONFIRMATION_REQUIRED",
                    )

                ok, msg = identity_manager.confirm_enrollment(name, confirmed=True)
                return ToolResult(
                    success=ok,
                    message=f"I have remembered {name}." if ok else msg,
                    data={"person_name": name, "status": EnrollmentStatus.KNOWN.value},
                )

            if action == "reject_person":
                name_target = name or "this person"
                ok, msg = identity_manager.confirm_enrollment(name_target, confirmed=False)
                return ToolResult(
                    success=True,
                    message="Understood. I will not save this person.",
                    data={"status": EnrollmentStatus.DO_NOT_REMEMBER.value},
                )

            if action == "forget_person":
                if not name:
                    return ToolResult(success=False, message="Please specify the name of the person to forget.", error_code="MISSING_NAME")
                ok = identity_manager.forget_person(name)
                if ok:
                    return ToolResult(success=True, message=f"I have forgotten {name}.", data={"forgotten": name})
                return ToolResult(success=False, message=f"No record found for {name}.", error_code="NOT_FOUND")

            if action == "forget_all":
                if not confirmed:
                    return ToolResult(
                        success=False,
                        message="Are you sure you want to forget all remembered people? This cannot be undone.",
                        data={"requires_confirmation": True, "action": "forget_all"},
                        error_code="CONFIRMATION_REQUIRED",
                    )
                ok = identity_manager.forget_all_persons(confirmed=True)
                return ToolResult(success=ok, message="I have forgotten all remembered identities.", data={"cleared": ok})

            return ToolResult(success=False, message=f"Unsupported action '{action}'.", error_code="INVALID_ACTION")

        except Exception as exc:
            logger.exception("IdentityTool execution failed: %s", exc)
            return ToolResult(success=False, message=f"Identity operation failed: {exc}", error_code="IDENTITY_ERROR")
