"""Unit tests for Windows UI Automation (UIA) Accessibility Subsystem."""

from __future__ import annotations

from backend.perception.ui_action_resolver import UIActionResolver
from backend.perception.ui_automation_engine import UIAutomationEngine, get_uia_metrics
from backend.perception.ui_automation_models import AccessibilityElement, InteractionMode


def test_uia_engine_enumeration_and_element_search():
    engine = UIAutomationEngine()
    elements = engine.find_all()

    assert len(elements) > 0

    el_save = engine.find_element("Save")
    assert el_save is not None
    assert el_save.name == "Save"

    el_none = engine.find_element("NonExistentControlNameXYZ")
    assert el_none is None


def test_uia_engine_native_pattern_interactions():
    engine = UIAutomationEngine()
    el = AccessibilityElement(name="Submit", role="Button", supports_invoke=True)

    assert engine.invoke(el) is True
    assert engine.set_value(el, "Hello World") is True
    assert engine.select(el) is True
    assert engine.focus(el) is True
    assert engine.expand(el) is True
    assert engine.collapse(el) is True


def test_ui_action_resolver_uia_first_priority_and_ocr_fallback():
    engine = UIAutomationEngine()
    resolver = UIActionResolver(uia_engine=engine)

    ref_uia = resolver.resolve_target("Click Save")
    assert ref_uia.target_phrase == "Save"
    assert ref_uia.confidence >= 0.90

    ref_ocr = resolver.resolve_target("Click NonExistentElementLabel")
    assert ref_ocr.target_phrase == "NonExistentElementLabel"
    assert ref_ocr.confidence == 0.85


def test_uia_metrics_and_telemetry_collection():
    engine = UIAutomationEngine()
    engine.find_element("Save")
    engine.find_element("MissingControl")

    metrics = get_uia_metrics()
    assert metrics["total_interactions"] >= 2
    assert metrics["accessibility_success_percent"] > 0
    assert metrics["average_lookup_latency_ms"] >= 0
