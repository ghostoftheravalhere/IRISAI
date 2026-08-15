"""Unit tests for SelectionManager stateful selection workflows."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from backend.automation.controller import DesktopController
from backend.automation.selection_manager import SelectionManager


@pytest.fixture
def mock_controller():
    controller = MagicMock(spec=DesktopController)
    controller.move_rel.return_value = True
    return controller


def test_selection_manager_start_and_stop(mock_controller):
    sm = SelectionManager(mock_controller)
    assert sm.get_state().is_selecting is False

    sm.start_selection(100.0, 200.0)
    assert sm.get_state().is_selecting is True
    assert sm.get_state().anchor_x == 100.0

    sm.update_position(300.0, 400.0)
    assert sm.get_state().current_x == 300.0

    sm.stop_selection(350.0, 450.0)
    assert sm.get_state().is_selecting is False
    assert mock_controller.move_rel.call_count >= 1
