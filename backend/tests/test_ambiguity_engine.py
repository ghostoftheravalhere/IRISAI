"""Unit tests for AmbiguityEngine candidate ranking and classification."""

from __future__ import annotations

import pytest
from backend.perception.ambiguity_engine import AmbiguityEngine, CandidateMatch


def test_ambiguity_engine_exact_match():
    engine = AmbiguityEngine()
    elements = [
        {"name": "Dev Nayi Clg", "x": 100.0, "y": 200.0, "type": "chat"},
        {"name": "General Chat", "x": 100.0, "y": 400.0, "type": "chat"},
    ]
    res = engine.resolve_candidates("Dev Nayi Clg", available_elements=elements)
    assert res.classification == "HIGH_CONFIDENCE"
    assert res.best_candidate is not None
    assert res.best_candidate.label == "Dev Nayi Clg"
    assert res.best_candidate.confidence_score >= 0.85


def test_ambiguity_engine_medium_confidence_confirmation():
    engine = AmbiguityEngine()
    elements = [
        {"name": "Dev Nayi Clg", "x": 100.0, "y": 200.0, "type": "chat"},
    ]
    # "Dev Clg" vs "Dev Nayi Clg" -> Medium confidence candidate match
    res = engine.resolve_candidates("Dev Clg", available_elements=elements)
    assert res.classification in {"MEDIUM_CONFIDENCE", "HIGH_CONFIDENCE", "MULTIPLE_CANDIDATES"}
    assert res.best_candidate is not None
    assert "Dev Nayi Clg" in res.best_candidate.label


def test_ambiguity_engine_multiple_candidates():
    engine = AmbiguityEngine()
    elements = [
        {"name": "Dev Nayi Clg", "x": 100.0, "y": 200.0, "type": "chat"},
        {"name": "Dev College Group", "x": 100.0, "y": 250.0, "type": "chat"},
    ]
    res = engine.resolve_candidates("Dev Clg", available_elements=elements)
    assert res.classification == "MULTIPLE_CANDIDATES"
    assert res.prompt_message is not None
    assert "multiple matches" in res.prompt_message.lower()


def test_ambiguity_engine_no_match():
    engine = AmbiguityEngine()
    elements = [
        {"name": "Settings", "x": 100.0, "y": 200.0, "type": "button"},
    ]
    res = engine.resolve_candidates("Calculator", available_elements=elements)
    assert res.classification == "NO_MATCH"
