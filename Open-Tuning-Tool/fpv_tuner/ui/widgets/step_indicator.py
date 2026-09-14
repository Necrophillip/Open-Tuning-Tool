"""
Step Indicator — vertical stepper showing wizard progress.

Each step shows: number/check circle, title, subtitle, and connector line.
Animated transitions between states.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

from fpv_tuner.ui.theme import Colors, Spacing, Radius, Typography, Timing


class StepState:
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    LOCKED = "locked"


_STATE_COLORS = {
    StepState.DONE: Colors.STEP_DONE,
    StepState.ACTIVE: Colors.STEP_ACTIVE,
    StepState.PENDING: Colors.STEP_PENDING,
    StepState.LOCKED: Colors.STEP_LOCKED,
}


class _StepCircle(QWidget):
    """A single numbered circle with animated state."""

    CIRCLE_SIZE = 32

    def __init__(self, number: int, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.CIRCLE_SIZE, self.CIRCLE_SIZE)
        self._number = number
        self._state = StepState.PENDING

    def set_state(self, state: str):
        self._state = state
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor(_STATE_COLORS.get(self._state, Colors.STEP_PENDING))
        rect = QRect(2, 2, self.CIRCLE_SIZE - 4, self.CIRCLE_SIZE - 4)

        if self._state == StepState.DONE:
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(rect)
            # Check mark
            pen = QPen(QColor(Colors.BG_APP), 2.5)
            painter.setPen(pen)
            cx, cy = self.CIRCLE_SIZE // 2, self.CIRCLE_SIZE // 2
            painter.drawLine(cx - 6, cy, cx - 2, cy + 4)
            painter.drawLine(cx - 2, cy + 4, cx + 5, cy - 5)
        elif self._state == StepState.ACTIVE:
            painter.setBrush(QColor(Colors.BG_SURFACE))
            pen = QPen(color, 2.5)
            painter.setPen(pen)
            painter.drawEllipse(rect)
            # Number in accent color
            painter.setPen(color)
            font = QFont()
            font.setPixelSize(14)
            font.setWeight(QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self._number))
        else:
            painter.setBrush(QColor(Colors.BG_SURFACE))
            pen = QPen(QColor(Colors.BORDER_SUBTLE), 1.5)
            painter.setPen(pen)
            painter.drawEllipse(rect)
            painter.setPen(QColor(_STATE_COLORS.get(self._state)))
            font = QFont()
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self._number))

        painter.end()


class StepIndicator(QWidget):
    """Vertical stepper with clickable steps."""

    step_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps: list[dict] = []
        self._step_widgets: list[dict] = []
        self._current = 0

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addStretch()

    def set_steps(self, steps: list[dict]):
        """
        steps: [{"title": str, "subtitle": str}, ...]
        """
        # Clear existing
        for w_dict in self._step_widgets:
            w_dict["container"].deleteLater()
        self._step_widgets.clear()
        self._steps = steps

        # Remove stretch, rebuild
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, step in enumerate(steps):
            container = QWidget()
            container.setCursor(Qt.CursorShape.PointingHandCursor)
            h_layout = QHBoxLayout(container)
            h_layout.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
            h_layout.setSpacing(Spacing.MD)

            circle = _StepCircle(i + 1)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)

            title = QLabel(step["title"])
            title.setStyleSheet(f"""
                color: {Colors.TEXT_SECONDARY};
                font-size: {Typography.SIZE_BODY}px;
                font-weight: 600;
            """)

            subtitle = QLabel(step.get("subtitle", ""))
            subtitle.setStyleSheet(f"""
                color: {Colors.TEXT_DISABLED};
                font-size: {Typography.SIZE_CAPTION}px;
            """)
            subtitle.setWordWrap(True)

            text_col.addWidget(title)
            text_col.addWidget(subtitle)

            h_layout.addWidget(circle)
            h_layout.addLayout(text_col, 1)

            # Connector line (except for last step)
            widgets = {
                "container": container,
                "circle": circle,
                "title": title,
                "subtitle": subtitle,
            }
            self._step_widgets.append(widgets)

            self._layout.addWidget(container)

            # Click handler
            container.mousePressEvent = lambda e, idx=i: self.step_clicked.emit(idx)

        self._layout.addStretch()
        self._update_states()

    def set_current(self, index: int, unlocked_up_to: int = None):
        """Set the active step and update all states."""
        self._current = index
        if unlocked_up_to is None:
            unlocked_up_to = index
        self._unlocked_up_to = unlocked_up_to
        self._update_states()

    def _update_states(self):
        for i, w in enumerate(self._step_widgets):
            if i < self._current:
                state = StepState.DONE
            elif i == self._current:
                state = StepState.ACTIVE
            elif i <= getattr(self, "_unlocked_up_to", self._current):
                state = StepState.PENDING
            else:
                state = StepState.LOCKED

            w["circle"].set_state(state)

            color = Colors.TEXT_PRIMARY if state in (StepState.ACTIVE, StepState.DONE) else Colors.TEXT_SECONDARY
            if state == StepState.LOCKED:
                color = Colors.TEXT_DISABLED
            w["title"].setStyleSheet(f"""
                color: {color};
                font-size: {Typography.SIZE_BODY}px;
                font-weight: 600;
            """)
