import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton,
    QFileDialog, QGroupBox, QLabel, QMessageBox, QComboBox, QScrollArea
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg
import numpy as np

from fpv_tuner.analysis.tuning import get_step_response
from fpv_tuner.blackbox.loader import load_log

class TuningTab(QWidget):
    bb_log_path = None
    loaded_logs = {}

    def __init__(self):
        super().__init__()
        main_layout = QHBoxLayout(self)

        # --- Left Panel ---
        left_panel_container = QWidget()
        left_panel_layout = QVBoxLayout(left_panel_container)
        self._create_load_controls(left_panel_layout)
        self._create_scope_controls(left_panel_layout)
        left_panel_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(left_panel_container)

        # --- Right Panel ---
        right_panel_layout = QVBoxLayout()
        self._create_plot_controls(right_panel_layout)

        # --- Main Layout Assembly ---
        main_layout.addWidget(scroll_area, 1)
        main_layout.addLayout(right_panel_layout, 4)

        self._connect_signals()

    def _create_load_controls(self, parent_layout):
        group = QGroupBox("1. Load Blackbox Log")
        layout = QVBoxLayout(group)
        self.bbl_load_widget = QWidget()
        bbl_load_layout = QHBoxLayout(self.bbl_load_widget)
        bbl_load_layout.setContentsMargins(0, 0, 0, 0)
        self.load_bb_button = QPushButton("Load .BBL File")
        self.load_bb_button.setFixedWidth(150)
        self.bb_file_label = QLabel("No file loaded.")
        bbl_load_layout.addWidget(self.load_bb_button)
        bbl_load_layout.addWidget(self.bb_file_label)
        self.bb_log_combo = QComboBox()
        bbl_load_layout.addWidget(self.bb_log_combo)
        self.bb_log_combo.setVisible(False)
        layout.addWidget(self.bbl_load_widget)
        parent_layout.addWidget(group)

    def _create_scope_controls(self, parent_layout):
        group = QGroupBox("2. Analysis Scope")
        layout = QFormLayout(group)
        self.axis_combo = QComboBox()
        self.axis_combo.addItems(["Roll", "Pitch", "Yaw"])
        layout.addRow("Axis:", self.axis_combo)
        parent_layout.addWidget(group)

    def _create_plot_controls(self, parent_layout):
        self.plot_widget = pg.PlotWidget(title="Step Response")
        self.plot_widget.addLegend()
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.setLabel('left', 'Normalized Response')
        self.plot_widget.showGrid(x=True, y=True)
        parent_layout.addWidget(self.plot_widget)

    def _connect_signals(self):
        self.load_bb_button.clicked.connect(self.on_load_blackbox)
        self.bb_log_combo.currentIndexChanged.connect(self.on_bbl_log_selected)
        self.axis_combo.currentTextChanged.connect(self.analyze_and_plot)

    def on_load_blackbox(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Blackbox Log", "", "Blackbox Logs (*.bbl *.bfl *.csv);;All Files (*)")
        if not filepath: return
        self.setCursor(Qt.CursorShape.WaitCursor)
        df, error = load_log(filepath)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if error:
            QMessageBox.critical(self, "Error Loading Log", error)
            return
        self.loaded_logs[filepath] = df
        self.bb_log_path = filepath
        self.bb_file_label.setText(os.path.basename(filepath))
        self.analyze_and_plot()

    def on_bbl_log_selected(self, index):
        filepath = self.bb_log_combo.itemData(index)
        self.bb_log_path = filepath
        if not filepath:
            self.clear_display()
            return
        self.bb_file_label.setText(os.path.basename(filepath))
        self.analyze_and_plot()

    def analyze_and_plot(self):
        if not self.bb_log_path or self.bb_log_path not in self.loaded_logs:
            self.clear_display()
            return

        self.plot_widget.clear()
        log_data = self.loaded_logs[self.bb_log_path]
        axis_to_analyze = self.axis_combo.currentText().lower()

        time, response = get_step_response(log_data.copy(), axis_to_analyze)

        if time is not None and response is not None:
            self.plot_widget.plot(time, response, pen={'color': 'g', 'width': 2}, name=f'{axis_to_analyze.capitalize()} Response')
        else:
            self.clear_display()
            text_item = pg.TextItem(f"Could not extract step response for '{axis_to_analyze.capitalize()}' axis.", anchor=(0.5, 0.5))
            self.plot_widget.addItem(text_item)

    def clear_display(self):
        self.plot_widget.clear()

    def set_data(self, logs):
        self.loaded_logs = logs
        self.bb_log_combo.clear()
        if logs:
            self.bb_log_combo.addItem("Select a loaded BBL...", userData=None)
            for path in logs.keys():
                self.bb_log_combo.addItem(os.path.basename(path), userData=path)
            self.load_bb_button.setVisible(False)
            self.bb_file_label.setVisible(False)
            self.bb_log_combo.setVisible(True)
        else:
            self.load_bb_button.setVisible(True)
            self.bb_file_label.setVisible(True)
            self.bb_log_combo.setVisible(False)
            self.clear_display()
            self.bb_log_path = None
            self.bb_file_label.setText("No file loaded.")