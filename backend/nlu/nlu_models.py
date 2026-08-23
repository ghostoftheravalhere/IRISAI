"""Natural Language Understanding Data Models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NLUEntity:
    """Extracted entity in conversational text."""

    entity_type: str  # "app", "query", "url", "file", "ordinal"
    value: str
    confidence: float = 1.0


@dataclass
class ParsedNLUIntent:
    """Full NLU parse result for an utterance."""

    intent_name: str
    target: str | None = None
    query: str | None = None
    confidence: float = 1.0
    entities: list[NLUEntity] = field(default_factory=list)
    sub_intents: list[ParsedNLUIntent] = field(default_factory=list)
    is_indirect: bool = False


@dataclass
class NLUBenchmarkSample:
    """Benchmark test case for accuracy evaluation."""

    utterance: str
    expected_intent: str
    expected_target: str | None = None
    expected_query: str | None = None
