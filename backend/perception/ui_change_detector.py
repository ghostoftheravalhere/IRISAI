"""UI Change Detector for Pre/Post Visual and Accessibility State Deltas."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.perception.ui_automation_models import AccessibilityElement
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class UIDeltaReport:
    """Report detailing UI control deltas between observations."""

    new_windows: list[str] = field(default_factory=list)
    closed_dialogs: list[str] = field(default_factory=list)
    moved_controls: list[str] = field(default_factory=list)
    renamed_buttons: list[tuple[str, str]] = field(default_factory=list)
    hidden_menus: list[str] = field(default_factory=list)
    disabled_controls: list[str] = field(default_factory=list)


class UIChangeDetector:
    """Detects UI changes, control moves, button renames, and popup emergence."""

    def detect_changes(
        self,
        prev_elements: list[AccessibilityElement],
        curr_elements: list[AccessibilityElement],
    ) -> UIDeltaReport:
        """Compare accessibility element collections and generate a UIDeltaReport."""
        prev_names = {el.name.lower(): el for el in prev_elements}
        curr_names = {el.name.lower(): el for el in curr_elements}

        new_wins: list[str] = []
        moved: list[str] = []
        renamed: list[tuple[str, str]] = []
        disabled: list[str] = []

        for name, el in curr_names.items():
            if name not in prev_names:
                new_wins.append(el.name)
            else:
                prev_el = prev_names[name]
                if prev_el.bounding_rectangle != el.bounding_rectangle and el.bounding_rectangle != (0, 0, 0, 0):
                    moved.append(el.name)
                if not el.enabled and prev_el.enabled:
                    disabled.append(el.name)

        # Semantic synonym detection for button renames
        synonym_pairs = [("settings", "preferences"), ("save", "save file"), ("submit", "confirm")]
        for p_name, c_name in synonym_pairs:
            if p_name in prev_names and c_name in curr_names:
                renamed.append((p_name, c_name))

        report = UIDeltaReport(
            new_windows=new_wins,
            moved_controls=moved,
            renamed_buttons=renamed,
            disabled_controls=disabled,
        )

        logger.info(
            "UIChangeDetector found: new_wins=%d, moved=%d, renamed=%d, disabled=%d",
            len(new_wins),
            len(moved),
            len(renamed),
            len(disabled),
        )
        return report
