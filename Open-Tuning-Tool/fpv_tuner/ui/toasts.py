"""
Toast notification system.

Shows temporary floating messages at the bottom of a parent widget.
Auto-dismisses after a configurable duration.
"""
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect, QFrame

from fpv_tuner.ui.theme import Colors, Spacing, Radius, Typography, Timing


class Toast(QFrame):
    """A single toast notification."""

    STYLES = {
        "success": {"bg": Colors.SUCCESS_MUTED, "border": Colors.SUCCESS, "icon": "check", "color": Colors.SUCCESS},
        "error":   {"bg": Colors.DANGER_MUTED,  "border": Colors.DANGER,  "icon": "x", "color": Colors.DANGER},
        "info":    {"bg": Colors.ACCENT_MUTED,   "border": Colors.ACCENT,  "icon": "info", "color": Colors.ACCENT},
        "warning": {"bg": Colors.WARNING_MUTED,  "border": Colors.WARNING, "icon": "alert", "color": Colors.WARNING},
    }

    def __init__(self, message: str, kind: str = "info",
                 duration_ms: int = 3000, parent=None):
        super().__init__(parent)
        style = self.STYLES.get(kind, self.STYLES["info"])
        
        from fpv_tuner.ui.icons import get_pixmap
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        layout.setSpacing(Spacing.MD)
        
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_pixmap(style["icon"], style["color"], 18))
        layout.addWidget(icon_lbl)
        
        txt_lbl = QLabel(message)
        txt_lbl.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(txt_lbl)

        self.setStyleSheet(f"""
            Toast {{
                background-color: {style['bg']};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {style['border']};
                border-radius: {Radius.LG}px;
                font-size: {Typography.SIZE_BODY}px;
            }}
        """)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.adjustSize()

        from fpv_tuner.ui.theme.effects import apply_shadow
        apply_shadow(self, blur=20, alpha=60)

        self._duration = duration_ms
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)

        self._opacity_effect.setOpacity(0)
        self.hide()

    def animate_in(self, y_offset: int):
        if not self.parent(): return
        
        x = (self.parent().width() - self.width()) // 2
        final_y = self.parent().height() - self.height() - y_offset
        start_y = final_y + 30
        
        self.move(x, start_y)
        self.show()

        from PyQt6.QtCore import QParallelAnimationGroup, QRect
        self._group_in = QParallelAnimationGroup(self)
        
        self._fade_in_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_in_anim.setDuration(Timing.NORMAL)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(1.0)
        self._fade_in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self._slide_in_anim = QPropertyAnimation(self, b"geometry", self)
        self._slide_in_anim.setDuration(Timing.NORMAL)
        self._slide_in_anim.setStartValue(QRect(x, start_y, self.width(), self.height()))
        self._slide_in_anim.setEndValue(QRect(x, final_y, self.width(), self.height()))
        self._slide_in_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        
        self._group_in.addAnimation(self._fade_in_anim)
        self._group_in.addAnimation(self._slide_in_anim)
        self._group_in.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        # Auto-dismiss
        QTimer.singleShot(self._duration, self._dismiss)

    def _dismiss(self):
        """Fade out then delete."""
        if not self.parent(): return
        from PyQt6.QtCore import QParallelAnimationGroup, QRect
        self._group_out = QParallelAnimationGroup(self)
        
        self._fade_out_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_out_anim.setDuration(Timing.FAST)
        self._fade_out_anim.setStartValue(1.0)
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        
        geo = self.geometry()
        self._slide_out_anim = QPropertyAnimation(self, b"geometry", self)
        self._slide_out_anim.setDuration(Timing.FAST)
        self._slide_out_anim.setStartValue(geo)
        self._slide_out_anim.setEndValue(QRect(geo.x(), geo.y() + 20, geo.width(), geo.height()))
        self._slide_out_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        
        self._group_out.addAnimation(self._fade_out_anim)
        self._group_out.addAnimation(self._slide_out_anim)
        self._group_out.finished.connect(self.deleteLater)
        self._group_out.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


class ToastManager:
    """Manages toast display on a parent widget."""

    def __init__(self, parent: QWidget):
        self._parent = parent
        self._active_toasts = []

    def show(self, message: str, kind: str = "info", duration_ms: int = 3000):
        """Show a toast.  kind: success, error, info, warning."""
        try:
            self._active_toasts = [t for t in self._active_toasts if t.parent()]
        except RuntimeError:
            self._active_toasts = []

        # Remove oldest if too many
        if len(self._active_toasts) > 4:
            oldest = self._active_toasts.pop(0)
            oldest.deleteLater()

        toast = Toast(message, kind, duration_ms, self._parent)
        
        # Calculate Y stacking
        total_height = 40  # base offset from bottom
        for t in reversed(self._active_toasts):
            total_height += t.height() + 10
            
        toast.animate_in(total_height)
        
        self._active_toasts.append(toast)
        
        # Slide existing toasts up (wait, actually new toasts stack on top)
        # So we don't need to slide existing toasts if we just stack the new ones above them.
        return toast

    def success(self, message: str, duration_ms: int = 3000):
        return self.show(message, "success", duration_ms)

    def error(self, message: str, duration_ms: int = 4000):
        return self.show(message, "error", duration_ms)

    def info(self, message: str, duration_ms: int = 3000):
        return self.show(message, "info", duration_ms)

    def warning(self, message: str, duration_ms: int = 3500):
        return self.show(message, "warning", duration_ms)

