"""LLM Planner Provider abstractions for local, cloud, and mock AI reasoning engines."""

from __future__ import annotations

import json
from typing import Any, Protocol

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class PlannerProvider(Protocol):
    """Protocol defining the interface for LLM plan generation providers."""

    @property
    def name(self) -> str:
        """Return provider identifier name."""
        ...

    def generate_plan(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Generate a raw candidate JSON plan string from prompt and context."""
        ...


class MockPlannerProvider:
    """Deterministic mock provider generating structured JSON plans for testing and offline fallback."""

    def __init__(self, name: str = "mock") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def generate_plan(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Return deterministic JSON plans based on keywords in prompt."""
        text = (prompt or "").lower()

        if "multi" in text:
            plan_dict = {
                "name": "Multi-Step Generated Plan",
                "steps": [
                    {"intent": "OPEN_CHROME", "target": "chrome"},
                    {"intent": "COPY", "rollback_intent": "PASTE"},
                ],
            }
        elif "notepad" in text:
            plan_dict = {
                "name": "Open Notepad Plan",
                "steps": [
                    {"intent": "OPEN_NOTEPAD", "target": "notepad"},
                ],
            }
        elif "invalid" in text or "hallucinated" in text:
            plan_dict = {
                "name": "Invalid Plan",
                "steps": [
                    {"intent": "UNKNOWN_HALLUCINATED_ACTION", "target": "magic"},
                ],
            }
        else:
            plan_dict = {
                "name": "Default Open Chrome Plan",
                "steps": [
                    {"intent": "OPEN_CHROME", "target": "chrome"},
                ],
            }
        return json.dumps(plan_dict)


class OllamaPlannerProvider:
    """Provider connecting to local Ollama HTTP REST API endpoint for local LLM planning."""

    def __init__(self, model_name: str = "llama3:8b", api_url: str = "http://localhost:11434") -> None:
        self._model_name = model_name
        self._api_url = api_url.rstrip("/")

    @property
    def name(self) -> str:
        return f"ollama:{self._model_name}"

    def generate_plan(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Attempt sending prompt to local Ollama service; fallback to Mock if unavailable."""
        try:
            import urllib.request

            req_data = json.dumps(
                {
                    "model": self._model_name,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                }
            ).encode("utf-8")

            url = f"{self._api_url}/api/generate"
            req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"})

            with urllib.request.urlopen(req, timeout=3.0) as response:
                if response.status == 200:
                    resp_json = json.loads(response.read().decode("utf-8"))
                    return resp_json.get("response", "{}")
        except Exception as exc:
            logger.warning("Ollama provider connection failed (%s); falling back to Mock.", exc)

        return MockPlannerProvider().generate_plan(prompt, context)
