"""Unit tests for Natural Conversation & Dialogue Manager."""

from __future__ import annotations

from backend.dialogue.clarification_manager import ClarificationManager
from backend.dialogue.conversation_policy import ConversationPolicy
from backend.dialogue.conversation_session import ConversationSession
from backend.dialogue.dialogue_manager import DialogueManager
from backend.dialogue.dialogue_models import DialoguePolicyAction, DialogueState
from backend.dialogue.reference_resolver import ReferenceResolver


def test_conversation_session_focus_stack():
    session = ConversationSession()
    session.push_focus("app", "chrome")
    session.push_focus("query", "DDCET syllabus")

    app = session.peek_focus("app")
    query = session.peek_focus("query")

    assert app is not None and app.value == "chrome"
    assert query is not None and query.value == "DDCET syllabus"


def test_reference_resolver_pronoun_binding():
    session = ConversationSession()
    session.push_focus("app", "chrome")
    session.push_focus("query", "DDCET syllabus")

    resolver = ReferenceResolver()

    # Test "Summarize it" -> "Summarize DDCET syllabus"
    text, target, query = resolver.resolve("Summarize it", session)
    assert "DDCET syllabus" in text
    assert target == "chrome"
    assert query == "DDCET syllabus"

    # Test "Search there" -> "Search in chrome"
    loc_text, loc_target, loc_query = resolver.resolve("Search there", session)
    assert "in chrome" in loc_text


def test_clarification_manager_and_policy():
    mgr = ClarificationManager()
    assert mgr.is_ambiguous(0.60) is True
    assert mgr.is_ambiguous(0.95) is False

    policy = ConversationPolicy()
    assert policy.evaluate(0.95, "BROWSER_SEARCH") == DialoguePolicyAction.DIRECT_EXECUTION
    assert policy.evaluate(0.50, "BROWSER_SEARCH") == DialoguePolicyAction.CLARIFY
    assert policy.evaluate(0.95, "SHUTDOWN_SYSTEM") == DialoguePolicyAction.CONFIRM


def test_dialogue_manager_multi_turn_flow():
    manager = DialogueManager()

    # Turn 1: Open Chrome
    res1 = manager.process_utterance("Open Chrome")
    assert res1["resolved_text"] == "Open Chrome"

    # Turn 2: Search DDCET syllabus
    res2 = manager.process_utterance("Search DDCET syllabus")
    assert res2["target"] == "chrome"
    assert res2["query"] == "DDCET syllabus"

    # Turn 3: Summarize it -> Pronoun "it" resolves to "DDCET syllabus"
    res3 = manager.process_utterance("Summarize it")
    assert "DDCET syllabus" in res3["resolved_text"]
