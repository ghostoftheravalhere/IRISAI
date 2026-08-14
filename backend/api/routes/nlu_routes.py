"""FastAPI Router for Natural Language Understanding Refinement."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.nlu.multi_intent_parser import MultiIntentParser
from backend.nlu.nlu_benchmark import NLUBenchmarkSuite

router = APIRouter(prefix="/nlu", tags=["nlu"])

# Shared singleton instances
_parser = MultiIntentParser()
_benchmark_suite = NLUBenchmarkSuite(parser=_parser)


class ParseRequest(BaseModel):
    text: str


@router.post("/parse")
def parse_utterance(req: ParseRequest):
    """Parse a conversational utterance into structured NLU intent & entities."""
    res = _parser.parse_utterance(req.text)
    return {
        "intent_name": res.intent_name,
        "target": res.target,
        "query": res.query,
        "confidence": res.confidence,
        "is_indirect": res.is_indirect,
        "entities": [{"type": e.entity_type, "value": e.value} for e in res.entities],
        "sub_intents_count": len(res.sub_intents),
    }


@router.post("/benchmark")
def run_nlu_benchmark():
    """Run NLU accuracy evaluation benchmark suite."""
    report = _benchmark_suite.run_benchmark()
    return report
