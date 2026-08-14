"""Hybrid Memory Retrieval & Relevance Ranking Pipeline."""

from __future__ import annotations

import time
from typing import Sequence

from backend.memory.embedding_service import LocalEmbeddingProvider
from backend.memory.knowledge_graph import KnowledgeGraphStore
from backend.memory.memory_models import MemoryItem, MemoryQueryResult
from backend.memory.vector_store import LocalVectorStore
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class HybridMemoryRetriever:
    """Hybrid memory retriever combining Vector Cosine Similarity, Recency, and Frequency."""

    def __init__(
        self,
        vector_store: LocalVectorStore,
        knowledge_graph: KnowledgeGraphStore,
        embedding_provider: LocalEmbeddingProvider,
        w_sim: float = 0.6,
        w_recency: float = 0.2,
        w_freq: float = 0.2,
    ) -> None:
        self._vector_store = vector_store
        self._knowledge_graph = knowledge_graph
        self._embedding_provider = embedding_provider
        self._w_sim = w_sim
        self._w_recency = w_recency
        self._w_freq = w_freq

    def retrieve(self, query: str, top_k: int = 5) -> list[MemoryQueryResult]:
        """Retrieve top-K memory items ranked by hybrid relevance score."""
        if not query:
            return []

        query_vec = self._embedding_provider.generate_embedding(query)
        candidates = self._vector_store.search(query_vec, top_k=top_k * 2)

        now = time.time()
        results: list[MemoryQueryResult] = []

        for item, sim in candidates:
            age_hours = max(0.1, (now - item.last_accessed_at) / 3600.0)
            recency_score = 1.0 / (1.0 + age_hours)
            freq_score = min(1.0, item.access_count / 10.0)

            combined = (
                self._w_sim * sim + self._w_recency * recency_score + self._w_freq * freq_score
            )

            results.append(
                MemoryQueryResult(
                    memory_item=item,
                    combined_score=combined,
                    similarity_score=sim,
                    recency_score=recency_score,
                    frequency_score=freq_score,
                )
            )

        results.sort(key=lambda x: x.combined_score, reverse=True)
        return results[:top_k]
