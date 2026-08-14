"""Central Memory Manager Subsystem Coordinator."""

from __future__ import annotations

from threading import RLock
import time
from typing import Sequence

from backend.core.events.bus import EventBus
from backend.memory.embedding_service import LocalEmbeddingProvider
from backend.memory.knowledge_graph import KnowledgeGraphStore
from backend.memory.memory_models import EntityRelation, MemoryItem, MemoryLayer, MemoryQueryResult
from backend.memory.memory_privacy import MemoryPrivacyFilter
from backend.memory.retrieval_pipeline import HybridMemoryRetriever
from backend.memory.vector_store import LocalVectorStore
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class MemoryManager:
    """Central manager coordinating 6 memory layers, embeddings, vector search, and Knowledge Graph."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        embedding_provider: LocalEmbeddingProvider | None = None,
        vector_store: LocalVectorStore | None = None,
        knowledge_graph: KnowledgeGraphStore | None = None,
        privacy_filter: MemoryPrivacyFilter | None = None,
        enabled: bool = True,
    ) -> None:
        self._event_bus = event_bus
        self._embedding_provider = embedding_provider or LocalEmbeddingProvider()
        self._vector_store = vector_store or LocalVectorStore()
        self._knowledge_graph = knowledge_graph or KnowledgeGraphStore()
        self._privacy_filter = privacy_filter or MemoryPrivacyFilter()
        self._retriever = HybridMemoryRetriever(
            self._vector_store,
            self._knowledge_graph,
            self._embedding_provider,
        )
        self._enabled = enabled
        self._lock = RLock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def remember(
        self,
        content: str,
        layer: MemoryLayer = MemoryLayer.SEMANTIC,
        tags: Sequence[str] | None = None,
        importance: float = 0.5,
        metadata: dict | None = None,
    ) -> MemoryItem:
        """Store a new sanitized semantic memory item."""
        with self._lock:
            sanitized = self._privacy_filter.sanitize_content(content)
            vec = self._embedding_provider.generate_embedding(sanitized)

            item = MemoryItem(
                content=sanitized,
                layer=layer,
                embedding=vec,
                tags=list(tags or []),
                importance=importance,
                metadata=dict(metadata or {}),
            )

            self._vector_store.add(item)
            logger.info("Memory stored [layer=%s]: %s...", layer.value, sanitized[:40])
            return item

    def recall(self, query: str, top_k: int = 5) -> list[MemoryQueryResult]:
        """Recall top-K relevant memories using hybrid retrieval."""
        with self._lock:
            return self._retriever.retrieve(query, top_k=top_k)

    def add_knowledge_relation(self, subject: str, relation: str, obj: str) -> EntityRelation:
        """Add an entity relationship triple to knowledge graph."""
        with self._lock:
            rel = EntityRelation(subject=subject, relation=relation, object=obj)
            self._knowledge_graph.add_relation(rel)
            return rel

    def forget_topic(self, topic: str) -> int:
        """Delete all memories matching a target topic phrase."""
        with self._lock:
            count = 0
            all_items = self._vector_store.list_all()
            for item in all_items:
                if self._privacy_filter.should_forget(item.content, topic):
                    self._vector_store.delete(item.memory_id)
                    count += 1
            logger.info("Forgot %d memory items for topic '%s'", count, topic)
            return count

    def list_memories(self, layer: MemoryLayer | None = None) -> list[MemoryItem]:
        """List stored memories optionally filtered by layer."""
        with self._lock:
            all_items = self._vector_store.list_all()
            if layer is not None:
                return [i for i in all_items if i.layer == layer]
            return all_items
