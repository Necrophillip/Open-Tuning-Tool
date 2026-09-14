"""
Toast notification system.

Shows temporary floating messages at the bottom of a parent widget.
Auto-dismisses after a configurable duration.
"""
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect

from fpv_tuner.ui.theme import Colors, Spacing, Radius, Typography, Timing


class Toast(QLabel):
    """A single toast notification."""

    STYLES = {
        "success": {"bg": Colors.SUCCESS_MUTED, "border": Colors.SUCCESS, "icon": "✅"},
        "error":   {"bg": Colors.DANGER_MUTED,  "border": Colors.DANGER,  "icon": "❌"},
        "info":    {"bg": Colors.ACCENT_MUTED,   "border": Colors.ACCENT,  "icon": "ℹ️"},
        "warning": {"bg": Colors.WARNING_MUTED,  "border": Colors.WARNING, "icon": "⚠️"},
    }

    def __init__(self, message: str, kind: str = "info",
                 duration_ms: int = 3000, parent=None):
        super().__init__(parent)
        style = self.STYLES.get(kind, self.STYLES["info"])
        self.setText(f"  {style['icon']}  {message}  ")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""
            background-color: {style['bg']};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {style['border']};
            border-radius: {Radius.LG}px;
            padding: {Spacing.SM}px {Spacing.LG}px;
            font-size: {Typography.SIZE_BODY}px;
        """)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.adjustSize()

        self._duration = duration_ms
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)

        # Position at bottom center of parent
        if parent:
            x = (parent.width() - self.width()) // 2
            y = parent.height() - self.height() - 80
            self.move(x, y)

        # Fade in
        self._fade_in_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_in_anim.setDuration(Timing.FAST)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(1.0)
        self._fade_in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_in_anim.start()
        self.show()

        # Auto-dismiss
        QTimer.singleShot(self._duration, self._dismiss)

    def _dismiss(self):
        """Fade out then delete."""
        self._fade_out_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_out_anim.setDuration(Timing.FAST)
        self._fade_out_anim.setStartValue(1.0)
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out_anim.finished.connect(self.deleteLater)
        self._fade_out_anim.start()


class ToastManager:
    """Manages toast display on a parent widget."""

    def __init__(self, parent: QWidget):
        self._parent = parent
        self._active_toasts = []

    def show(self, message: str, kind: str = "info", duration_ms: int = 3000):
        """Show a toast.  kind: success, error, info, warning."""
        # Clean up deleted toasts (avoid RuntimeError on C++ deleted objects)
        try:
            self._active_toasts = [t for t in self._active_toasts if t.parent()]
        except RuntimeError:
            self._active_toasts = []

        toast = Toast(message, kind, duration_ms, self._parent)
        self._active_toasts.append(toast)
        return toast

    def success(self, message: str, duration_ms: int = 3000):
        return self.show(message, "success", duration_ms)

    def error(self, message: str, duration_ms: int = 4000):
        return self.show(message, "error", duration_ms)

    def info(self, message: str, duration_ms: int = 3000):
        return self.show(message, "info", duration_ms)

    def warning(self, message: str, duration_ms: int = 3500):
        return self.show(message, "warning", duration_ms)
