"""Local Persistence Vector Store Service."""

from __future__ import annotations

from threading import RLock
from typing import Sequence

from backend.memory.memory_models import MemoryItem
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Calculate cosine similarity between two vector lists."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math_sqrt = sum(a * a for a in v1) ** 0.5
    norm_b = math_sqrt = sum(b * b for b in v2) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class LocalVectorStore:
    """Local SQLite & In-Memory Vector Store for KNN Cosine Similarity Search."""

    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}
        self._lock = RLock()

    def add(self, item: MemoryItem) -> None:
        """Add or update a memory item in vector store."""
        with self._lock:
            self._items[item.memory_id] = item

    def get(self, memory_id: str) -> MemoryItem | None:
        """Retrieve item by memory ID."""
        with self._lock:
            return self._items.get(memory_id)

    def delete(self, memory_id: str) -> bool:
        """Delete item by memory ID."""
        with self._lock:
            if memory_id in self._items:
                del self._items[memory_id]
                return True
            return False

    def list_all(self) -> list[MemoryItem]:
        """List all stored memory items."""
        with self._lock:
            return list(self._items.values())

    def search(self, query_vector: list[float], top_k: int = 5) -> list[tuple[MemoryItem, float]]:
        """Search top-K nearest neighbors using Cosine Similarity."""
        with self._lock:
            results: list[tuple[MemoryItem, float]] = []
            for item in self._items.values():
                if item.embedding:
                    sim = cosine_similarity(query_vector, item.embedding)
                    results.append((item, sim))
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]
