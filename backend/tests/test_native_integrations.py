"""Unit tests for Native Application Integrations Subsystem."""

from __future__ import annotations

from backend.brain.skills.base import SkillExecutionContext
from backend.brain.skills.browser_skill import BrowserSkill
from backend.brain.skills.file_explorer_skill import FileExplorerSkill
from backend.brain.skills.git_skill import GitIntegrationSkill
from backend.brain.skills.github_skill import GitHubSkill
from backend.brain.skills.notion_skill import NotionSkill
from backend.brain.skills.spotify_skill import SpotifySkill
from backend.brain.skills.vscode_skill import VSCodeSkill


def test_vscode_skill():
    skill = VSCodeSkill()
    assert skill.can_handle("OPEN_VSCODE_PROJECT") is True

    res = skill.execute(SkillExecutionContext(intent="OPEN_VSCODE_PROJECT", params={"path": "."}))
    assert res.success is True


def test_git_skill():
    skill = GitIntegrationSkill()
    assert skill.can_handle("GIT_STATUS") is True

    res = skill.execute(SkillExecutionContext(intent="GIT_STATUS"))
    assert res.success is True
    assert "Git branch" in res.message


def test_github_skill():
    skill = GitHubSkill()
    assert skill.can_handle("CREATE_GITHUB_ISSUE") is True

    res = skill.execute(SkillExecutionContext(intent="CREATE_GITHUB_ISSUE", params={"title": "Fix bug"}))
    assert res.success is True


def test_browser_and_spotify_skills():
    b_skill = BrowserSkill()
    assert b_skill.can_handle("OPEN_BROWSER_TAB") is True
    b_res = b_skill.execute(SkillExecutionContext(intent="OPEN_BROWSER_TAB", params={"query": "python.org"}))
    assert b_res.success is True

    s_skill = SpotifySkill()
    assert s_skill.can_handle("PLAY_SPOTIFY") is True
    s_res = s_skill.execute(SkillExecutionContext(intent="PLAY_SPOTIFY"))
    assert s_res.success is True


def test_notion_and_file_explorer_skills():
    n_skill = NotionSkill()
    assert n_skill.can_handle("OPEN_NOTION_PAGE") is True
    n_res = n_skill.execute(SkillExecutionContext(intent="OPEN_NOTION_PAGE"))
    assert n_res.success is True

    f_skill = FileExplorerSkill()
    assert f_skill.can_handle("SEARCH_FILES") is True
    f_res = f_skill.execute(SkillExecutionContext(intent="SEARCH_FILES"))
    assert f_res.success is True
