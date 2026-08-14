"""Unit tests for Sprint 10 Plugin & Skill Framework."""

from __future__ import annotations

from backend.automation.controller import DesktopController
from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.skills.base import (
    SkillDescriptor,
    SkillExecutionContext,
    SkillResult,
)
from backend.brain.skills.builtin import DesktopAutomationSkill, MediaControlSkill
from backend.brain.skills.events import (
    SkillExecutionCompletedEvent,
    SkillRegisteredEvent,
)
from backend.brain.skills.registry import SkillRegistry, SkillValidator
from backend.config.settings import settings
from backend.core.di.container import build_container
from backend.core.events.bus import EventBus


class _FakeDesktop(DesktopController):
    def open_application(self, app_name: str) -> bool:
        return True

    def hotkey(self, *keys: str) -> bool:
        return True

    def press(self, key: str, presses: int = 1) -> bool:
        return True

    def mute(self) -> bool:
        return True


def test_builtin_skills_registration_and_discovery():
    dispatcher = AutomationDispatcher(_FakeDesktop())
    registry = SkillRegistry(enabled=True)

    desktop_skill = DesktopAutomationSkill(dispatcher)
    media_skill = MediaControlSkill(dispatcher)

    registry.register_skill(desktop_skill)
    registry.register_skill(media_skill)

    descriptors = registry.discover_skills()
    assert len(descriptors) == 2
    skill_ids = [d.skill_id for d in descriptors]
    assert "desktop_automation" in skill_ids
    assert "media_control" in skill_ids


def test_skill_registry_finds_and_executes_by_intent():
    dispatcher = AutomationDispatcher(_FakeDesktop())
    registry = SkillRegistry(enabled=True)
    registry.register_skill(DesktopAutomationSkill(dispatcher))

    res = registry.execute_intent("OPEN_CHROME", params={"target": "chrome"})
    assert res.success is True
    assert res.result_data["intent"] == "OPEN_CHROME"


def test_skill_permission_validation_strict_mode():
    dispatcher = AutomationDispatcher(_FakeDesktop())
    skill = DesktopAutomationSkill(dispatcher)

    # Valid permission
    valid_ctx = SkillExecutionContext(intent="OPEN_CHROME", user_permissions=["desktop:control"])
    is_valid, _ = SkillValidator.validate(skill, valid_ctx, strict_permissions=True)
    assert is_valid is True

    # Missing permission
    invalid_ctx = SkillExecutionContext(intent="OPEN_CHROME", user_permissions=[])
    is_valid, reason = SkillValidator.validate(skill, invalid_ctx, strict_permissions=True)
    assert is_valid is False
    assert "Permission denied" in reason


def test_skill_registry_event_bus_emission():
    event_bus = EventBus()
    events_captured = []

    event_bus.subscribe(SkillRegisteredEvent, lambda e: events_captured.append(e))
    event_bus.subscribe(SkillExecutionCompletedEvent, lambda e: events_captured.append(e))

    dispatcher = AutomationDispatcher(_FakeDesktop())
    registry = SkillRegistry(event_bus=event_bus, enabled=True)
    registry.register_skill(MediaControlSkill(dispatcher))

    res = registry.execute_intent("MUTE")
    assert res.success is True
    assert len(events_captured) == 2
    assert isinstance(events_captured[0], SkillRegisteredEvent)
    assert isinstance(events_captured[1], SkillExecutionCompletedEvent)


def test_di_container_wires_skill_registry():
    container = build_container(settings)
    assert container.skill_registry is not None
    assert container.skill_registry.enabled is True
    assert len(container.skill_registry.discover_skills()) >= 2
