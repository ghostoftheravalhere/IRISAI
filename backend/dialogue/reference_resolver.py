"""Reference & Pronoun Resolver Service."""

from __future__ import annotations

import re
from typing import Sequence

from backend.dialogue.conversation_session import ConversationSession
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Pronoun and implicit reference patterns
_PRONOUN_PATTERNS = re.compile(r"\b(?:it|that|this|the item|the pdf|the document)\b", re.IGNORECASE)
_LOCATION_PATTERNS = re.compile(r"\b(?:there|in there|on it)\b", re.IGNORECASE)


from backend.context.world_model import DesktopWorldState, WorldModel, _WORLD_MODEL_METRICS


class ReferenceResolver:
    """Resolves implicit pronouns ('it', 'that', 'this', 'second one') using WorldModel and focus stack entities."""

    def __init__(self, world_model: WorldModel | None = None) -> None:
        self._world_model = world_model

    def resolve(
        self,
        raw_text: str,
        session: ConversationSession,
        current_target: str | None = None,
        current_query: str | None = None,
        world_state: DesktopWorldState | None = None,
    ) -> tuple[str, str | None, str | None]:
        """Resolve pronouns and return (resolved_text, resolved_target, resolved_query)."""
        if not raw_text:
            return raw_text, current_target, current_query

        _WORLD_MODEL_METRICS["reference_resolutions"] += 1
        resolved_text = raw_text
        resolved_target = current_target
        resolved_query = current_query

        ws = world_state or (self._world_model.current_state if self._world_model else None)

        # Contextual WorldModel inspection for "this" / "it" / "close it"
        if ws:
            lower = raw_text.lower()
            if "summarize" in lower or "this" in lower:
                if ws.selected_text:
                    resolved_query = ws.selected_text
                    _WORLD_MODEL_METRICS["successful_resolutions"] += 1
                    logger.info("ReferenceResolver bound 'this' -> selected text '%s'", ws.selected_text)
                elif ws.visible_documents:
                    resolved_query = ws.visible_documents[0]
                    _WORLD_MODEL_METRICS["successful_resolutions"] += 1
                    logger.info("ReferenceResolver bound 'this' -> document '%s'", ws.visible_documents[0])
            elif "close" in lower and ("it" in lower or "dialog" in lower):
                if ws.visible_dialogs:
                    resolved_target = ws.visible_dialogs[-1]
                    _WORLD_MODEL_METRICS["successful_resolutions"] += 1
                    logger.info("ReferenceResolver bound 'close it' -> dialog '%s'", ws.visible_dialogs[-1])
            elif "second" in lower:
                if len(ws.visible_browser_tabs) >= 2:
                    resolved_query = ws.visible_browser_tabs[1]
                    _WORLD_MODEL_METRICS["successful_resolutions"] += 1
                    logger.info("ReferenceResolver bound 'second one' -> tab '%s'", ws.visible_browser_tabs[1])

        # Step 1: Resolve target application if missing but referenced ("there", "in Chrome")
        if not resolved_target:
            app_focus = session.peek_focus("app")
            if app_focus:
                resolved_target = app_focus.value

        # Step 2: Resolve pronouns ("it", "that") using query focus
        if _PRONOUN_PATTERNS.search(raw_text):
            query_focus = session.peek_focus("query")
            if query_focus:
                resolved_query = resolved_query or query_focus.value
                resolved_text = _PRONOUN_PATTERNS.sub(query_focus.value, resolved_text)
                _WORLD_MODEL_METRICS["successful_resolutions"] += 1
                logger.info("ReferenceResolver bound pronoun 'it/that' -> '%s'", query_focus.value)

        # Step 3: Resolve location ("there") using app focus
        if _LOCATION_PATTERNS.search(raw_text):
            app_focus = session.peek_focus("app")
            if app_focus:
                resolved_text = _LOCATION_PATTERNS.sub(f"in {app_focus.value}", resolved_text)
                logger.info("ReferenceResolver bound location 'there' -> '%s'", app_focus.value)

        return resolved_text, resolved_target, resolved_query
