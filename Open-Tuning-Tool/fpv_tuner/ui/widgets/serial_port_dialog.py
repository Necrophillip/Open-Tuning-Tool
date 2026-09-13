"""
Serial port selection dialog.

Lets the user pick the flight controller's serial device from a list of
available ports (refreshed on demand).  Pure presentation — port
enumeration lives in ``fpv_tuner.core.serial.ports``.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QDialogButtonBox,
)
from PyQt6.QtCore import Qt

from fpv_tuner.ui.theme import Colors, Spacing, Radius, Typography
from fpv_tuner.core.serial.ports import list_serial_ports, SerialPortInfo


class SerialPortDialog(QDialog):
    """Modal dialog that returns the chosen serial device path."""

    def __init__(self, parent=None, title: str = "Select Flight Controller"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(420, 320)
        self._selected: str | None = None

        self._build_ui()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.MD)

        title = QLabel("Select serial device")
        title.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: {Typography.SIZE_HEADING}px;
            font-weight: 700;
        """)
        layout.addWidget(title)

        subtitle = QLabel(
            "Connect your flight controller via USB, then pick its serial port."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Typography.SIZE_BODY}px;")
        layout.addWidget(subtitle)

        self.port_list = QListWidget()
        self.port_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Radius.MD}px;
                color: {Colors.TEXT_PRIMARY};
                font-size: {Typography.SIZE_BODY}px;
                padding: {Spacing.SM}px;
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
        self.port_list.itemDoubleClicked.connect(lambda _: self._accept())
        layout.addWidget(self.port_list, 1)

        # Refresh + status row
        row = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: {Typography.SIZE_CAPTION}px;"
        )
        row.addWidget(self.status_label, 1)

        self.refresh_btn = QPushButton("↻  Refresh")
        self.refresh_btn.setProperty("variant", "ghost")
        self.refresh_btn.clicked.connect(self._refresh)
        row.addWidget(self.refresh_btn)
        layout.addLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        self.ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_btn.setEnabled(False)
        self.ok_btn.setText("Connect")
        layout.addWidget(buttons)

        self.port_list.currentItemChanged.connect(self._on_selection)

    # ── Logic ─────────────────────────────────────────────────────

    def _refresh(self):
        self.port_list.clear()
        ports = list_serial_ports()
        if not ports:
            self.status_label.setText("No serial ports detected — plug in the FC and refresh.")
            self.ok_btn.setEnabled(False)
            return

        for info in ports:
            item = QListWidgetItem(info.label)
            item.setData(Qt.ItemDataRole.UserRole, info.device)
            self.port_list.addItem(item)
        self.status_label.setText(f"{len(ports)} device(s) found")
        if ports:
            self.port_list.setCurrentRow(0)

    def _on_selection(self, current, _previous):
        self.ok_btn.setEnabled(current is not None)

    def _accept(self):
        item = self.port_list.currentItem()
        if item is None:
            return
        self._selected = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    @property
    def selected_port(self) -> str | None:
        return self._selected

    @staticmethod
    def get_port(parent=None, title: str = "Select Flight Controller") -> str | None:
        """Convenience: open the dialog and return the chosen port (or None)."""
        dialog = SerialPortDialog(parent, title)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_port
        return None
