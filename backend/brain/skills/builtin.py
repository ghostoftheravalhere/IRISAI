"""Built-in core skills wrapping desktop automation and media capabilities."""

from __future__ import annotations

from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.skills.base import (
    SkillDescriptor,
    SkillExecutionContext,
    SkillResult,
)
from backend.voice.command_parser import VoiceIntent, VoiceIntentType


class DesktopAutomationSkill:
    """Built-in Skill providing desktop application and input interaction capabilities."""

    def __init__(self, dispatcher: AutomationDispatcher) -> None:
        self._dispatcher = dispatcher
        self._descriptor = SkillDescriptor(
            skill_id="desktop_automation",
            name="Desktop Automation Skill",
            version="1.0.0",
            description="Controls desktop applications, input focus, and clipboard actions.",
            required_permissions=["desktop:control"],
            capabilities=[
                "OPEN_APPLICATION",
                "CLOSE_APPLICATION",
                "OPEN_CHROME",
                "OPEN_NOTEPAD",
                "COPY",
                "PASTE",
                "SELECT_ALL",
                "MINIMIZE_WINDOW",
                "CLOSE_WINDOW",
                "SCROLL_DOWN",
                "SCROLL_UP",
                "BROWSER_SEARCH",
                "HOTKEY",
                "TYPE_TEXT",
                "PRESS_KEY",
                "WAIT_FOR_WINDOW",
                "ACTIVATE_WINDOW",
                "VERIFY_WINDOW_ACTIVE",
            ],
        )

    @property
    def descriptor(self) -> SkillDescriptor:
        """Return SkillDescriptor."""
        return self._descriptor

    def can_execute(self, context: SkillExecutionContext) -> tuple[bool, str]:
        """Validate if requested intent capability is supported."""
        if context.intent in self._descriptor.capabilities:
            return True, "Supported desktop automation capability."
        return False, f"Capability '{context.intent}' not supported by desktop_automation skill."

    def execute(self, context: SkillExecutionContext) -> SkillResult:
        """Execute desktop automation capability via AutomationDispatcher."""
        intent_enum = VoiceIntentType.NO_INTENT
        for member in VoiceIntentType:
            if member.value == context.intent:
                intent_enum = member
                break

        target = context.params.get("target") or context.params.get("application")
        query = context.params.get("query")
        voice_intent = VoiceIntent(
            intent=intent_enum,
            text=context.raw_transcript or context.intent,
            target=target,
            query=query,
            params=context.params,
        )
        result = self._dispatcher.dispatch(voice_intent)

        return SkillResult(
            success=result.success,
            message=result.message,
            result_data={"intent": result.intent.value},
        )


class MediaControlSkill:
    """Built-in Skill providing system volume, mute, and screenshot capabilities."""

    def __init__(self, dispatcher: AutomationDispatcher) -> None:
        self._dispatcher = dispatcher
        self._descriptor = SkillDescriptor(
            skill_id="media_control",
            name="Media & System Control Skill",
            version="1.0.0",
            description="Manages audio playback volume, mute state, and desktop screenshots.",
            required_permissions=["system:media"],
            capabilities=[
                "VOLUME_UP",
                "VOLUME_DOWN",
                "MUTE",
                "TAKE_SCREENSHOT",
            ],
        )

    @property
    def descriptor(self) -> SkillDescriptor:
        """Return SkillDescriptor."""
        return self._descriptor

    def can_execute(self, context: SkillExecutionContext) -> tuple[bool, str]:
        """Validate if requested intent capability is supported."""
        if context.intent in self._descriptor.capabilities:
            return True, "Supported media control capability."
        return False, f"Capability '{context.intent}' not supported by media_control skill."

    def execute(self, context: SkillExecutionContext) -> SkillResult:
        """Execute media control capability via AutomationDispatcher."""
        intent_enum = VoiceIntentType.NO_INTENT
        for member in VoiceIntentType:
            if member.value == context.intent:
                intent_enum = member
                break

        voice_intent = VoiceIntent(intent=intent_enum, text=context.raw_transcript)
        result = self._dispatcher.dispatch(voice_intent)

        return SkillResult(
            success=result.success,
            message=result.message,
            result_data={"intent": result.intent.value},
        )
