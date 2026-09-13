"""
Blackbox file selection dialog.

Shown when more than one per-flight ``.BBL`` file is found on the FC (the
combined "all" file is already excluded).  Lists name, size and date, and
returns the chosen path.
"""
from datetime import datetime
import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem,
    QDialogButtonBox, QHBoxLayout,
)
from PyQt6.QtCore import Qt

from fpv_tuner.ui.theme import Colors, Spacing, Radius, Typography


class BblSelectDialog(QDialog):
    """Modal dialog to pick one blackbox file."""

    def __init__(self, files: list[dict], parent=None):
        """
        Args:
            files: list of dicts with keys ``path``, ``name``, ``size``, ``date``.
        """
        super().__init__(parent)
        self.setWindowTitle("Select Blackbox Log")
        self.setMinimumSize(460, 360)
        self._selected = None
        self._build_ui(files)

    def _build_ui(self, files):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.MD)

        title = QLabel("Select a blackbox log")
        title.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: {Typography.SIZE_HEADING}px;
            font-weight: 700;
        """)
        layout.addWidget(title)

        subtitle = QLabel(
            "Your log is split into multiple files (one per arm/disarm). "
            "Choose the flight you want to analyze."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Typography.SIZE_BODY}px;")
        layout.addWidget(subtitle)

        self.file_list = QListWidget()
        self.file_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Radius.MD}px;
                color: {Colors.TEXT_PRIMARY};
                font-size: {Typography.SIZE_BODY}px;
            }}
            QListWidget::item {{
                padding: {Spacing.SM}px;
                border-radius: {Radius.SM}px;
            }}
            QListWidget::item:selected {{
                background-color: {Colors.ACCENT_MUTED};
                color: {Colors.ACCENT};
            }}
        """)
        self.file_list.itemDoubleClicked.connect(lambda _: self._accept())

        for f in files:
            item = QListWidgetItem(f"{f['name']}    ({f['size']}  ·  {f['date']})")
            item.setData(Qt.ItemDataRole.UserRole, f["path"])
            self.file_list.addItem(item)

        # Select the most recent file by default (files are pre-sorted newest-first).
        if self.file_list.count():
            self.file_list.setCurrentRow(0)
        layout.addWidget(self.file_list, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        self.ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_btn.setText("Load")
        layout.addWidget(buttons)

    def _accept(self):
        item = self.file_list.currentItem()
        if item is None:
            return
        self._selected = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    @property
    def selected_path(self):
        return self._selected

    @staticmethod
    def choose(files: list[dict], parent=None):
        """Open the dialog and return the chosen path (or None)."""
        dialog = BblSelectDialog(files, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_path
        return None


def describe_blackbox_file(path: str) -> dict:
    """Build the {path, name, size, date} dict used by the dialog."""
    name = os.path.basename(path)
    try:
        size = os.path.getsize(path)
        size_str = f"{size / (1024 * 1024):.1f} MB" if size > 1024 * 1024 else f"{size // 1024} KB"
    except OSError:
        size_str = "?"
    try:
        date_str = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%b %d, %H:%M")
    except OSError:
        date_str = "?"
    return {"path": path, "name": name, "size": size_str, "date": date_str}
