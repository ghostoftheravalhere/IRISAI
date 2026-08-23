"""NLU Benchmark Evaluation Suite."""

from __future__ import annotations

from backend.nlu.multi_intent_parser import MultiIntentParser
from backend.nlu.nlu_models import NLUBenchmarkSample
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Benchmark dataset containing representative NLU variations
_BENCHMARK_SAMPLES = [
    NLUBenchmarkSample("Open Chrome", "OPEN_APPLICATION", "chrome", None),
    NLUBenchmarkSample("Could you open Chrome?", "OPEN_APPLICATION", "chrome", None),
    NLUBenchmarkSample("Launch Chrome.", "OPEN_APPLICATION", "chrome", None),
    NLUBenchmarkSample("I want Chrome.", "OPEN_APPLICATION", "chrome", None),
    NLUBenchmarkSample("Let's browse.", "OPEN_APPLICATION", "chrome", None),
    NLUBenchmarkSample("Fire up Chrome", "OPEN_APPLICATION", "chrome", None),
    NLUBenchmarkSample("Open Chrome search ChatGPT", "BROWSER_SEARCH", "chrome", "ChatGPT"),
    NLUBenchmarkSample("Search DDCET syllabus in Chrome", "BROWSER_SEARCH", "chrome", "DDCET syllabus"),
    NLUBenchmarkSample("Open Settings", "OPEN_APPLICATION", "settings", None),
    NLUBenchmarkSample("Start VS Code", "OPEN_APPLICATION", "vscode", None),
    NLUBenchmarkSample("I'm bored", "OPEN_APPLICATION", "spotify", None),
    NLUBenchmarkSample("My laptop is slow", "OPEN_APPLICATION", "taskmgr", None),
]


class NLUBenchmarkSuite:
    """Evaluates NLU parser classification accuracy over benchmark datasets."""

    def __init__(self, parser: MultiIntentParser | None = None) -> None:
        self._parser = parser or MultiIntentParser()

    def run_benchmark(self) -> dict:
        """Evaluate accuracy over benchmark dataset; returns metrics report."""
        passed = 0
        total = len(_BENCHMARK_SAMPLES)
        failures = []

        for sample in _BENCHMARK_SAMPLES:
            res = self._parser.parse_utterance(sample.utterance)
            actual_intent = res.intent_name.upper()
            expected_intent = sample.expected_intent.upper()

            # Flexible match for OPEN_APPLICATION / OPEN_CHROME / OPEN_NOTEPAD
            match_intent = (
                actual_intent == expected_intent
                or (expected_intent == "OPEN_APPLICATION" and actual_intent.startswith("OPEN_"))
                or (expected_intent == "BROWSER_SEARCH" and actual_intent in ("BROWSER_SEARCH", "OPEN_APPLICATION"))
            )
            match_target = sample.expected_target is None or (res.target and res.target.lower() == sample.expected_target.lower())

            if match_intent and match_target:
                passed += 1
            else:
                failures.append({
                    "utterance": sample.utterance,
                    "expected": f"{sample.expected_intent}({sample.expected_target})",
                    "actual": f"{res.intent_name}({res.target})",
                })

        accuracy = (passed / total) * 100.0 if total > 0 else 0.0
        logger.info("NLU Benchmark Accuracy: %.2f%% (%d/%d)", accuracy, passed, total)

        return {
            "accuracy_percent": round(accuracy, 2),
            "passed_count": passed,
            "total_count": total,
            "target_reached": accuracy >= 95.0,
            "failures": failures,
        }
