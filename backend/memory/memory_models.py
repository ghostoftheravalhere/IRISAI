"""Semantic Memory & Knowledge System Data Models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any
import uuid


class MemoryLayer(str, Enum):
    """Memory stratification layers."""

    WORKING = "WORKING"
    SESSION = "SESSION"
    EPISODIC = "EPISODIC"
    SEMANTIC = "SEMANTIC"
    WORKSPACE = "WORKSPACE"
    PREFERENCE = "PREFERENCE"


@dataclass
class MemoryItem:
    """Individual unit of structured semantic memory."""

    content: str
    layer: MemoryLayer
    memory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    embedding: list[float] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    importance: float = 0.5
    created_at: float = field(default_factory=time.time)
    last_accessed_at: float = field(default_factory=time.time)
    access_count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EntityRelation:
    """Knowledge Graph triple relationship model."""

    subject: str
    relation: str
    object: str
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)


@dataclass
class MemoryQueryResult:
    """Ranked search result item from hybrid memory retrieval."""

    memory_item: MemoryItem
    combined_score: float
    similarity_score: float = 0.0
    recency_score: float = 0.0
    frequency_score: float = 0.0
