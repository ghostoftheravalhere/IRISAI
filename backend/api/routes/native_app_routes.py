"""FastAPI Router for Native Application Integrations."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.brain.skills.base import SkillExecutionContext
from backend.brain.skills.browser_skill import BrowserSkill
from backend.brain.skills.file_explorer_skill import FileExplorerSkill
from backend.brain.skills.git_skill import GitIntegrationSkill
from backend.brain.skills.github_skill import GitHubSkill
from backend.brain.skills.notion_skill import NotionSkill
from backend.brain.skills.spotify_skill import SpotifySkill
from backend.brain.skills.vscode_skill import VSCodeSkill

router = APIRouter(prefix="/integrations", tags=["integrations"])

# Shared Skill instances
_vscode = VSCodeSkill()
_git = GitIntegrationSkill()
_github = GitHubSkill()
_browser = BrowserSkill()
_spotify = SpotifySkill()
_notion = NotionSkill()
_file_explorer = FileExplorerSkill()


class ActionRequest(BaseModel):
    action: str
    target: str = "."


@router.get("/status")
def get_integrations_status():
    """Get status of all registered native application skill plugins."""
    skills = [_vscode, _git, _github, _browser, _spotify, _notion, _file_explorer]
    return {
        "count": len(skills),
        "integrations": [
            {
                "skill_id": s.descriptor.skill_id,
                "name": s.descriptor.name,
                "capabilities": s.descriptor.capabilities,
            }
            for s in skills
        ],
    }


@router.post("/vscode")
def execute_vscode(req: ActionRequest):
    """Execute a VS Code integration action."""
    res = _vscode.execute(SkillExecutionContext(intent=req.action, params={"path": req.target}))
    return {"success": res.success, "message": res.message, "data": res.result_data}


@router.post("/git")
def execute_git(req: ActionRequest):
    """Execute a Git integration action."""
    res = _git.execute(SkillExecutionContext(intent=req.action, params={"path": req.target}))
    return {"success": res.success, "message": res.message, "data": res.result_data}


@router.post("/github")
def execute_github(req: ActionRequest):
    """Execute a GitHub integration action."""
    res = _github.execute(SkillExecutionContext(intent=req.action, params={"title": req.target}))
    return {"success": res.success, "message": res.message, "data": res.result_data}
