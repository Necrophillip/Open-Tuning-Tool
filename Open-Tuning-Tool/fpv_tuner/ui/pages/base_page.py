"""
Base class for all wizard pages.

Each page implements:
  - on_enter():  called when the page becomes visible
  - can_proceed():  whether the "Next" button should be enabled
  - title / subtitle:  shown in the step indicator
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

from fpv_tuner.ui.theme import Colors, Spacing, Typography
from fpv_tuner.ui.app_state import AppState


class WizardPage(QWidget):
    """Base class for wizard step pages."""

    # Subclasses must set these
    STEP_TITLE: str = "Step"
    STEP_SUBTITLE: str = ""

    # Emitted when the page's validity changes (enables/disables Next)
    validity_changed = pyqtSignal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._build_ui()

    # ── Contract ──────────────────────────────────────────────────

    def on_enter(self):
        """Called when this page becomes the current step."""

    def can_proceed(self) -> bool:
        """Return True when the user may advance to the next step."""
        return True

    # ── Helpers ───────────────────────────────────────────────────

    def _build_ui(self):
        """Override in subclasses. Called once from __init__."""

    def _make_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: {Typography.SIZE_TITLE}px;
            font-weight: 700;
        """)
        return label

    def _make_subtitle(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SIZE_BODY}px;
            line-height: 1.5;
        """)
        return label

    def _make_card(self) -> QWidget:
        """A surface-level container for grouping content."""
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 14px;
            }}
        """)
        return card
