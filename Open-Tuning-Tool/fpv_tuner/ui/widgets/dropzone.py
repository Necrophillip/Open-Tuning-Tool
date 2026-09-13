"""
DropZone — animated drag & drop target.

States:
  idle    → dashed border, muted icon + hint
  hover   → accent border pulse, icon lifts
  success → green check with ripple
  error   → red flash with shake
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve,
    QTimer, QRectF, QPointF
)
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QDragEnterEvent, QDropEvent

from fpv_tuner.ui.theme import Colors, Spacing, Radius, Typography, Timing


class DropZone(QFrame):
    """Drag & drop zone with animated feedback."""

    files_dropped = pyqtSignal(list)   # list of file paths

    VALID_EXTENSIONS = ()

    def __init__(self, title="Drop file here", subtitle="or click to browse",
                 icon="📂", valid_extensions=(), parent=None):
        super().__init__(parent)
        self.VALID_EXTENSIONS = tuple(e.lower() for e in valid_extensions)
        self._icon = icon
        self._state = "idle"
        self._pulse_opacity = 0.0
        self._accept_drops = True

        self.setAcceptDrops(True)
        self.setMinimumHeight(200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("dropZone")
        self._apply_style()

        # ── Layout ──
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(Spacing.SM)

        self._icon_label = QLabel(icon)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet("font-size: 48px; background: transparent; border: none;")

        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: {Typography.SIZE_HEADING}px;
            font-weight: 600;
            background: transparent;
            border: none;
        """)

        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SIZE_BODY}px;
            background: transparent;
            border: none;
        """)

        self._detail_label = QLabel("")
        self._detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_label.setStyleSheet(f"""
            color: {Colors.TEXT_DISABLED};
            font-size: {Typography.SIZE_CAPTION}px;
            background: transparent;
            border: none;
        """)
        self._detail_label.hide()

        layout.addWidget(self._icon_label)
        layout.addWidget(self._title_label)
        layout.addWidget(self._subtitle_label)
        layout.addWidget(self._detail_label)

        # Pulse animation for hover state
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_tick)
        self._pulse_direction = 1

    # ── Styling ───────────────────────────────────────────────────

    def _apply_style(self):
        border_color = {
            "idle": Colors.BORDER_SUBTLE,
            "hover": Colors.ACCENT,
            "success": Colors.SUCCESS,
            "error": Colors.DANGER,
        }.get(self._state, Colors.BORDER_SUBTLE)

        bg = {
            "idle": Colors.BG_SURFACE,
            "hover": Colors.ACCENT_MUTED,
            "success": Colors.SUCCESS_MUTED,
            "error": Colors.DANGER_MUTED,
        }.get(self._state, Colors.BG_SURFACE)

        self.setStyleSheet(f"""
            DropZone#dropZone {{
                background-color: {bg};
                border: 2px dashed {border_color};
                border-radius: {Radius.LG}px;
            }}
        """)

    # ── State transitions ─────────────────────────────────────────

    def set_state(self, state: str, detail: str = ""):
        self._state = state
        self._apply_style()
        if detail:
            self._detail_label.setText(detail)
            self._detail_label.show()
        else:
            self._detail_label.hide()

        if state == "hover":
            self._pulse_timer.start(50)
        else:
            self._pulse_timer.stop()
            self._pulse_opacity = 0.0

    def set_success(self, filename: str, detail: str = ""):
        self._icon_label.setText("✅")
        self._title_label.setText(filename)
        self._subtitle_label.setText("Loaded successfully — drop another to replace")
        self.set_state("success", detail)

    def set_error(self, message: str):
        self._icon_label.setText("❌")
        self.set_state("error", message)
        # Auto-reset after 3 seconds
        QTimer.singleShot(3000, self.reset)

    def reset(self):
        self._icon_label.setText(self._icon)
        self._title_label.setText("Drop file here")
        self._subtitle_label.setText("or click to browse")
        self.set_state("idle")

    def set_enabled(self, enabled: bool):
        self._accept_drops = enabled
        self.setAcceptDrops(enabled)
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ForbiddenCursor)

    # ── Pulse animation ───────────────────────────────────────────

    def _pulse_tick(self):
        self._pulse_opacity += 0.05 * self._pulse_direction
        if self._pulse_opacity >= 0.3:
            self._pulse_direction = -1
        elif self._pulse_opacity <= 0.0:
            self._pulse_direction = 1
        self.update()

    # ── Drag & Drop events ────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if not self._accept_drops:
            event.ignore()
            return
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(self._is_valid(u.toLocalFile()) for u in urls):
                event.acceptProposedAction()
                self.set_state("hover")
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        if self._state == "hover":
            self.set_state("idle")

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if self._is_valid(u.toLocalFile())]
        if paths:
            self.files_dropped.emit(paths)
        else:
            self.set_error(f"Invalid file type. Expected: {', '.join(self.VALID_EXTENSIONS)}")
        if self._state == "hover":
            self.set_state("idle")

    def _is_valid(self, path: str) -> bool:
        if not self.VALID_EXTENSIONS:
            return True
        return any(path.lower().endswith(ext) for ext in self.VALID_EXTENSIONS)

    def mousePressEvent(self, event):
        """Click to browse."""
        if event.button() == Qt.MouseButton.LeftButton and self._accept_drops:
            self._open_file_dialog()

    def _open_file_dialog(self):
        from PyQt6.QtWidgets import QFileDialog
        filter_str = " ".join(f"*{e}" for e in self.VALID_EXTENSIONS) or "*"
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select File", "", f"Supported Files ({filter_str})"
        )
        if paths:
            valid = [p for p in paths if self._is_valid(p)]
            if valid:
                self.files_dropped.emit(valid)
            else:
                self.set_error(f"Invalid file type. Expected: {', '.join(self.VALID_EXTENSIONS)}")
