"""Unit tests for DialogueManager state machine and confirmation/clarification turns."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from backend.automation.action_engine import ActionEngine
from backend.automation.action_models import ActionRequest, CanonicalAction
from backend.brain.dialogue_manager import DialogueManager, DialogueState
from backend.perception.ambiguity_engine import AmbiguityEngine, AmbiguityResolution, CandidateMatch


@pytest.fixture
def mock_action_engine():
    engine = MagicMock(spec=ActionEngine)
    engine.execute.return_value = MagicMock(success=True, message="Action executed")
    return engine


def test_dialogue_manager_direct_execution(mock_action_engine):
    ambiguity_mock = MagicMock(spec=AmbiguityEngine)
    ambiguity_mock.resolve_candidates.return_value = AmbiguityResolution(
        classification="HIGH_CONFIDENCE",
        best_candidate=CandidateMatch("Chrome", 100.0, 100.0, 0.95, "Match", "button"),
        candidates=(),
    )
    dm = DialogueManager(action_engine=mock_action_engine, ambiguity_engine=ambiguity_mock)
    req = ActionRequest(action=CanonicalAction.OPEN_APPLICATION, target_phrase="chrome")
    res = dm.process_utterance("Open Chrome", voice_request=req)
    assert res.state == DialogueState.IDLE
    assert res.executed_result is not None
    mock_action_engine.execute.assert_called_once()


def test_dialogue_manager_confirmation_flow(mock_action_engine):
    ambiguity_mock = MagicMock(spec=AmbiguityEngine)
    candidate = CandidateMatch("Dev Nayi Clg", 100.0, 200.0, 0.75, "Fuzzy match", "chat")
    ambiguity_mock.resolve_candidates.return_value = AmbiguityResolution(
        classification="MEDIUM_CONFIDENCE",
        best_candidate=candidate,
        candidates=(candidate,),
        prompt_message="I found 'Dev Nayi Clg'. Do you want me to open it?",
    )

    dm = DialogueManager(action_engine=mock_action_engine, ambiguity_engine=ambiguity_mock)
    req = ActionRequest(action=CanonicalAction.OPEN_APPLICATION, target_phrase="Dev Clg")

    # Turn 1: Triggers AWAITING_CONFIRMATION
    turn1 = dm.process_utterance("Open Dev Clg", voice_request=req)
    assert turn1.state == DialogueState.AWAITING_CONFIRMATION
    assert "Dev Nayi Clg" in turn1.prompt_message

    # Turn 2: User says "Yes"
    turn2 = dm.process_utterance("Yes")
    assert turn2.state == DialogueState.IDLE
    assert turn2.executed_result is not None
    mock_action_engine.execute.assert_called_once()


def test_dialogue_manager_clarification_flow(mock_action_engine):
    ambiguity_mock = MagicMock(spec=AmbiguityEngine)
    c1 = CandidateMatch("Dev Nayi Clg", 100.0, 200.0, 0.70, "Fuzzy match", "chat")
    c2 = CandidateMatch("Dev College Group", 100.0, 250.0, 0.68, "Fuzzy match", "chat")
    ambiguity_mock.resolve_candidates.return_value = AmbiguityResolution(
        classification="MULTIPLE_CANDIDATES",
        best_candidate=c1,
        candidates=(c1, c2),
        prompt_message="I found multiple matches: 1. Dev Nayi Clg, 2. Dev College Group. Which one?",
    )

    dm = DialogueManager(action_engine=mock_action_engine, ambiguity_engine=ambiguity_mock)
    req = ActionRequest(action=CanonicalAction.OPEN_APPLICATION, target_phrase="Dev Clg")

    # Turn 1: Triggers AWAITING_CLARIFICATION
    turn1 = dm.process_utterance("Open Dev Clg", voice_request=req)
    assert turn1.state == DialogueState.AWAITING_CLARIFICATION

    # Turn 2: User says "Second one"
    turn2 = dm.process_utterance("Second one")
    assert turn2.state == DialogueState.IDLE
    assert turn2.executed_result is not None
    assert mock_action_engine.execute.call_args[0][0].target_phrase == "Dev College Group"


def test_dialogue_manager_cancel_flow(mock_action_engine):
    ambiguity_mock = MagicMock(spec=AmbiguityEngine)
    c1 = CandidateMatch("Dev Nayi Clg", 100.0, 200.0, 0.75, "Fuzzy match", "chat")
    ambiguity_mock.resolve_candidates.return_value = AmbiguityResolution(
        classification="MEDIUM_CONFIDENCE",
        best_candidate=c1,
        candidates=(c1,),
        prompt_message="I found 'Dev Nayi Clg'. Open it?",
    )

    dm = DialogueManager(action_engine=mock_action_engine, ambiguity_engine=ambiguity_mock)
    req = ActionRequest(action=CanonicalAction.OPEN_APPLICATION, target_phrase="Dev Clg")
    dm.process_utterance("Open Dev Clg", voice_request=req)

    # User says "No"
    turn2 = dm.process_utterance("No")
    assert turn2.state == DialogueState.IDLE
    assert turn2.cancelled is True
    mock_action_engine.execute.assert_not_called()
