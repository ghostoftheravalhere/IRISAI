"""Unit tests for Natural Language Understanding Refinement Subsystem."""

from __future__ import annotations

from backend.nlu.entity_extractor import EntityExtractor
from backend.nlu.indirect_intent_mapper import IndirectIntentMapper
from backend.nlu.multi_intent_parser import MultiIntentParser
from backend.nlu.nlu_benchmark import NLUBenchmarkSuite
from backend.nlu.synonym_engine import SynonymEngine


def test_synonym_engine_normalization():
    engine = SynonymEngine()
    assert "open chrome" in engine.normalize("Could you open Chrome?").lower()
    assert "open chrome" in engine.normalize("Launch Chrome").lower()
    assert "open vscode" in engine.normalize("Start code editor").lower()
    assert "open spotify" in engine.normalize("Start music").lower()


def test_entity_extractor():
    extractor = EntityExtractor()
    entities = extractor.extract_entities("Open Chrome search DDCET syllabus in Chrome")

    assert len(entities) >= 1
    assert any(e.value == "chrome" for e in entities)


def test_indirect_intent_mapper():
    mapper = IndirectIntentMapper()
    res1 = mapper.map_indirect("I'm bored")
    assert res1 is not None and res1.target == "spotify"

    res2 = mapper.map_indirect("My laptop is slow")
    assert res2 is not None and res2.target == "taskmgr"


def test_multi_intent_parser_and_benchmark():
    parser = MultiIntentParser()

    # Single intent
    res1 = parser.parse_utterance("Launch Chrome")
    assert res1.target == "chrome"

    # Multi-intent compound
    res2 = parser.parse_utterance("Open Chrome and search ChatGPT")
    assert len(res2.sub_intents) == 2

    # Benchmark evaluation
    benchmark = NLUBenchmarkSuite(parser=parser)
    report = benchmark.run_benchmark()
    assert report["accuracy_percent"] >= 95.0
