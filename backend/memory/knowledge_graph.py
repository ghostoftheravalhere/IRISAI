"""Knowledge Graph Entity Relationship Store."""

from __future__ import annotations

from threading import RLock
from typing import Sequence

from backend.memory.memory_models import EntityRelation
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class KnowledgeGraphStore:
    """In-Memory and Local SQLite Entity Relationship Graph Store."""

    def __init__(self) -> None:
        self._relations: list[EntityRelation] = []
        self._lock = RLock()

    def add_relation(self, relation: EntityRelation) -> None:
        """Add an entity relationship triple to knowledge graph."""
        with self._lock:
            self._relations.append(relation)

    def get_relations_for_entity(self, entity_name: str) -> list[EntityRelation]:
        """Find all triples involving the given entity as subject or object."""
        with self._lock:
            target = entity_name.strip().lower()
            return [
                r
                for r in self._relations
                if r.subject.strip().lower() == target or r.object.strip().lower() == target
            ]

    def list_all(self) -> list[EntityRelation]:
        """List all stored knowledge graph triples."""
        with self._lock:
            return list(self._relations)
