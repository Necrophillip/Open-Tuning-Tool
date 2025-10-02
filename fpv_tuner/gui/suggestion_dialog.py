from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QDialogButtonBox, QWidget, QTextEdit, QGroupBox, QHBoxLayout
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg

class SuggestionDialog(QDialog):
    def __init__(self, current_pids, suggested_pids, axis, cli_commands, real_response_data, suggested_response_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Tuning Suggestion for {axis.capitalize()} Axis")
        self.setMinimumWidth(600)
        self.setMinimumHeight(700)

        main_layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()

        # --- PID Comparison Table ---
        pid_group = QGroupBox("PID Comparison")
        pid_layout = QGridLayout(pid_group)
        headers = ["", "P", "I", "D", "F"]
        for i, header in enumerate(headers):
            pid_layout.addWidget(QLabel(f"<b>{header}</b>"), 0, i)

        # Current PIDs
        pid_layout.addWidget(QLabel("<b>Current</b>"), 1, 0)
        for i, term in enumerate(["p", "i", "d", "f"]):
            key = f"{term}_{axis}"
            pid_layout.addWidget(QLabel(str(current_pids.get(key, 'N/A'))), 1, i + 1)

        # Suggested PIDs
        pid_layout.addWidget(QLabel("<b>Suggested</b>"), 2, 0)
        for i, term in enumerate(["p", "i", "d", "f"]):
            key = f"{term}_{axis}"
            label = QLabel(str(suggested_pids.get(key, 'N/A')))
            if current_pids.get(key) != suggested_pids.get(key):
                label.setStyleSheet("color: #2ca02c; font-weight: bold;")
            pid_layout.addWidget(label, 2, i + 1)

        left_layout.addWidget(pid_group)

        # --- CLI Commands ---
        cli_group = QGroupBox("Generated CLI Commands")
        cli_layout = QVBoxLayout(cli_group)
        cli_text = QTextEdit()
        cli_text.setReadOnly(True)
        cli_text.setText(cli_commands)
        cli_text.setFontFamily("monospace")
        cli_layout.addWidget(cli_text)
        left_layout.addWidget(cli_group)

        # --- Dialog Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        left_layout.addWidget(button_box)

        # --- Comparison Plot ---
        plot_widget = pg.PlotWidget()
        plot_widget.addLegend()
        plot_widget.setLabel('bottom', 'Time (s)')
        plot_widget.setLabel('left', 'Normalized Response')
        plot_widget.plot(real_response_data['time'], real_response_data['response'], pen={'color': 'r', 'width': 2}, name='Real Response')
        plot_widget.plot(suggested_response_data['time'], suggested_response_data['response'], pen={'color': 'g', 'style': Qt.PenStyle.DashLine, 'width': 2}, name='Suggested Response')
        plot_widget.addItem(pg.InfiniteLine(pos=1.0, angle=0, movable=False, pen={'color': 'w', 'style': Qt.PenStyle.DashLine}))

        main_layout.addLayout(left_layout, 1)
        main_layout.addWidget(plot_widget, 2)