"""Local Vector Embedding Provider Service."""

from __future__ import annotations

import math
from typing import Sequence

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_VECTOR_DIM = 384


class LocalEmbeddingProvider:
    """Fast local 384-dimensional vector embedding generator."""

    def __init__(self, dimension: int = _DEFAULT_VECTOR_DIM) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def generate_embedding(self, text: str) -> list[float]:
        """Generate a normalized 384-dimensional vector representation for input text."""
        if not text:
            return [0.0] * self._dimension

        # Deterministic lightweight hash vector generation for offline execution
        vector = [0.0] * self._dimension
        words = text.strip().lower().split()
        for idx, word in enumerate(words):
            hash_val = sum(ord(c) * (i + 1) for i, c in enumerate(word))
            dim_idx = hash_val % self._dimension
            vector[dim_idx] += 1.0 / (idx + 1)

        # L2 normalize vector
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector
