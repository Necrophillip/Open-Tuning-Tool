from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QTextEdit, QPushButton, QDialogButtonBox
)
import pyqtgraph as pg
from PyQt6.QtCore import Qt

class SuggestionDialog(QDialog):
    def __init__(self, current_pids, suggested_pids, axis, cli_commands, real_response_data, suggested_response_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Tuning Suggestion for {axis.capitalize()} Axis")
        self.setMinimumSize(800, 600)

        main_layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)

        # --- Left Panel (PIDs and CLI) ---
        left_layout = QVBoxLayout()
        self._create_pid_table(left_layout, current_pids, suggested_pids, axis)
        self._create_cli_view(left_layout, cli_commands)
        top_layout.addLayout(left_layout, 1)

        # --- Right Panel (Plots) ---
        self._create_plot_view(top_layout, real_response_data, suggested_response_data)
        top_layout.addLayout(self._plot_group, 2)

        # --- Dialog Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box)

    def _create_pid_table(self, parent_layout, current_pids, suggested_pids, axis):
        pid_group = QGroupBox("PID Value Changes")
        layout = QVBoxLayout(pid_group)

        table = QTableWidget()
        table.setRowCount(4)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Term", "Current", "Suggested"])
        table.setVerticalHeaderLabels(["P", "I", "D", "F"])

        for i, term in enumerate(['p', 'i', 'd', 'f']):
            key = f"{term}_{axis}"
            current_val = current_pids.get(key, 'N/A')
            suggested_val = suggested_pids.get(key, 'N/A')

            table.setItem(i, 0, QTableWidgetItem(term.upper()))
            table.setItem(i, 1, QTableWidgetItem(str(current_val)))
            table.setItem(i, 2, QTableWidgetItem(str(suggested_val)))

        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        parent_layout.addWidget(pid_group)

    def _create_cli_view(self, parent_layout, cli_commands):
        cli_group = QGroupBox("Generated CLI Commands")
        layout = QVBoxLayout(cli_group)

        cli_text = QTextEdit()
        cli_text.setReadOnly(True)
        cli_text.setText(cli_commands)
        cli_text.setFontFamily("monospace")

        layout.addWidget(cli_text)
        parent_layout.addWidget(cli_group)

    def _create_plot_view(self, parent_layout, real_data, suggested_data):
        self._plot_group = QGroupBox("Comparison Plot")
        layout = QVBoxLayout(self._plot_group)

        plot_widget = pg.PlotWidget()
        plot_widget.addLegend()
        plot_widget.setLabel('bottom', 'Time (s)')
        plot_widget.setLabel('left', 'Normalized Response')
        plot_widget.showGrid(x=True, y=True)
        plot_widget.addItem(pg.InfiniteLine(pos=1.0, angle=0, movable=False, pen={'color': 'w', 'style': Qt.PenStyle.DashLine}))

        if real_data:
            plot_widget.plot(real_data["time"], real_data["response"], pen='r', name='Original Response')

        if suggested_data:
            plot_widget.plot(suggested_data["time"], suggested_data["response"], pen='g', name='Suggested Response')

        layout.addWidget(plot_widget)
        parent_layout.addWidget(self._plot_group)