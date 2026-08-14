"""Stateful Conversation Session & Focus Stack Manager."""

from __future__ import annotations

from threading import RLock
from typing import Sequence

from backend.dialogue.dialogue_models import DialogueState, DialogueTurn, FocusStackItem
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationSession:
    """Manages multi-turn conversation history and entity focus stack."""

    def __init__(self, max_turns: int = 50) -> None:
        self._max_turns = max_turns
        self._turns: list[DialogueTurn] = []
        self._focus_stack: list[FocusStackItem] = []
        self._state = DialogueState.IDLE
        self._lock = RLock()

    @property
    def state(self) -> DialogueState:
        return self._state

    def set_state(self, state: DialogueState) -> None:
        with self._lock:
            self._state = state

    def add_turn(self, turn: DialogueTurn) -> None:
        """Add a conversational turn and update focus stack."""
        with self._lock:
            self._turns.append(turn)
            if len(self._turns) > self._max_turns:
                self._turns.pop(0)

            # Automatically push targets onto focus stack
            turn_idx = len(self._turns) - 1
            if turn.resolved_target:
                self.push_focus("app", turn.resolved_target, turn_idx)
            if turn.resolved_query:
                self.push_focus("query", turn.resolved_query, turn_idx)

    def push_focus(self, entity_type: str, value: str, turn_index: int | None = None) -> None:
        """Push an entity onto the focus stack (top = most recent)."""
        with self._lock:
            idx = turn_index if turn_index is not None else len(self._turns)
            item = FocusStackItem(entity_type=entity_type, value=value, turn_index=idx)
            # Remove duplicate focus value if present
            self._focus_stack = [f for f in self._focus_stack if f.value.lower() != value.lower()]
            self._focus_stack.insert(0, item)

    def peek_focus(self, entity_type: str | None = None) -> FocusStackItem | None:
        """Retrieve the top focus item matching entity_type or overall top."""
        with self._lock:
            if not self._focus_stack:
                return None
            if entity_type is None:
                return self._focus_stack[0]
            for item in self._focus_stack:
                if item.entity_type == entity_type:
                    return item
            return None

    def get_history(self) -> list[DialogueTurn]:
        """Return full turn history."""
        with self._lock:
            return list(self._turns)

    def reset(self) -> None:
        """Reset conversation session state and focus stack."""
        with self._lock:
            self._turns.clear()
            self._focus_stack.clear()
            self._state = DialogueState.IDLE
            logger.info("Conversation session reset.")
