import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton,
    QFileDialog, QGroupBox, QLabel, QMessageBox, QComboBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg
import numpy as np

from fpv_tuner.analysis.tuning import get_step_response, calculate_response_metrics
from fpv_tuner.blackbox.loader import load_log

class TuningTab(QWidget):
    loaded_logs = {}
    plot_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

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
        self._create_metrics_display(right_panel_layout)

        # --- Main Layout Assembly ---
        main_layout.addWidget(scroll_area, 1)
        main_layout.addLayout(right_panel_layout, 4)

        self._connect_signals()

    def _create_load_controls(self, parent_layout):
        group = QGroupBox("1. Load Logs")
        layout = QVBoxLayout(group)

        self.load_bb_button = QPushButton("Add Blackbox Log(s)...")
        self.load_bb_button.setToolTip("Add one or more logs to the comparison.")
        layout.addWidget(self.load_bb_button)

        self.loaded_files_label = QLabel("No logs loaded.")
        self.loaded_files_label.setWordWrap(True)
        layout.addWidget(self.loaded_files_label)

        self.clear_logs_button = QPushButton("Clear Plotted Logs")
        layout.addWidget(self.clear_logs_button)

        parent_layout.addWidget(group)

    def _create_scope_controls(self, parent_layout):
        group = QGroupBox("2. Analysis Scope")
        layout = QFormLayout(group)
        self.axis_combo = QComboBox()
        self.axis_combo.addItems(["Roll", "Pitch", "Yaw"])
        layout.addRow("Axis:", self.axis_combo)
        parent_layout.addWidget(group)

    def _create_plot_controls(self, parent_layout):
        self.plot_widget = pg.PlotWidget(title="Step Response Comparison")
        self.plot_widget.addLegend()
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.setLabel('left', 'Normalized Response')
        self.plot_widget.showGrid(x=True, y=True)

        self.reference_line = pg.InfiniteLine(pos=1.0, angle=0, movable=False, pen={'color': 'w', 'style': Qt.PenStyle.DashLine})
        self.plot_widget.addItem(self.reference_line)

        parent_layout.addWidget(self.plot_widget, 2)

    def _create_metrics_display(self, parent_layout):
        group = QGroupBox("Performance Metrics")
        layout = QVBoxLayout(group)
        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(4)
        self.metrics_table.setHorizontalHeaderLabels(["File", "Overshoot (%)", "Rise Time (s)", "Settling Time (s)"])
        self.metrics_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.metrics_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.metrics_table.verticalHeader().setVisible(False)
        self.metrics_table.setMaximumHeight(150)
        layout.addWidget(self.metrics_table)
        parent_layout.addWidget(group)

    def _connect_signals(self):
        self.load_bb_button.clicked.connect(self.on_load_blackbox)
        self.clear_logs_button.clicked.connect(self.on_clear_logs)
        self.axis_combo.currentTextChanged.connect(self.analyze_and_plot)

    def on_load_blackbox(self):
        filepaths, _ = QFileDialog.getOpenFileNames(self, "Open Blackbox Log(s)", "", "Blackbox Logs (*.bbl *.bfl *.csv);;All Files (*)")
        if not filepaths:
            return

        for path in filepaths:
            if path in self.loaded_logs:
                continue # Skip already loaded files

            self.setCursor(Qt.CursorShape.WaitCursor)
            df, error = load_log(path)
            self.setCursor(Qt.CursorShape.ArrowCursor)

            if error:
                QMessageBox.critical(self, "Error Loading Log", f"Failed to load {os.path.basename(path)}:\n{error}")
                continue # Continue to next file

            self.loaded_logs[path] = df

        self._update_loaded_files_label()
        self.analyze_and_plot()

    def on_clear_logs(self):
        self.loaded_logs.clear()
        self._update_loaded_files_label()
        self.clear_display()

    def analyze_and_plot(self):
        self.plot_widget.clear()
        self.plot_widget.addItem(self.reference_line)
        if not self.loaded_logs:
            self.clear_display()
            return

        axis_to_analyze = self.axis_combo.currentText().lower()
        all_metrics_data = []
        max_settling_time = 0.4

        for i, (path, log_data) in enumerate(self.loaded_logs.items()):
            color = self.plot_colors[i % len(self.plot_colors)]
            filename = os.path.basename(path)

            time, response = get_step_response(log_data.copy(), axis_to_analyze)

            if time is not None and response is not None:
                self.plot_widget.plot(time, response, pen={'color': color, 'width': 2}, name=filename)
                metrics = calculate_response_metrics(time, response)
                metrics['filename'] = filename
                all_metrics_data.append(metrics)

                settling_time = metrics.get('Settling Time (s)', 0)
                if not np.isnan(settling_time) and settling_time > max_settling_time:
                    max_settling_time = settling_time
            else:
                print(f"Warning: Could not extract step response for {filename} on axis {axis_to_analyze}")

        self._update_metrics_table(all_metrics_data)

        if not all_metrics_data:
            self.clear_display()
            text_item = pg.TextItem(f"Could not extract step response for '{axis_to_analyze.capitalize()}' axis from any log.", anchor=(0.5, 0.5))
            self.plot_widget.addItem(text_item)
        else:
            self.plot_widget.setXRange(0, max_settling_time * 1.1, padding=0)
            self.plot_widget.setYRange(-0.2, 1.8, padding=0)

    def _update_metrics_table(self, metrics_data):
        self.metrics_table.setRowCount(len(metrics_data))
        for row, data in enumerate(metrics_data):
            self.metrics_table.setItem(row, 0, QTableWidgetItem(data.get('filename', 'N/A')))
            self.metrics_table.setItem(row, 1, QTableWidgetItem(f"{data.get('Overshoot (%)', 0):.2f}"))
            self.metrics_table.setItem(row, 2, QTableWidgetItem(f"{data.get('Rise Time (s)', 0):.4f}"))
            self.metrics_table.setItem(row, 3, QTableWidgetItem(f"{data.get('Settling Time (s)', 0):.4f}"))

    def clear_display(self):
        self.plot_widget.clear()
        self.plot_widget.addItem(self.reference_line)
        self.metrics_table.setRowCount(0)

    def _update_loaded_files_label(self):
        if not self.loaded_logs:
            self.loaded_files_label.setText("No logs loaded.")
        else:
            filenames = [os.path.basename(path) for path in self.loaded_logs.keys()]
            self.loaded_files_label.setText(f"Loaded: {', '.join(filenames)}")

    def set_data(self, logs):
        self.loaded_logs = logs
        self._update_loaded_files_label()
        self.analyze_and_plot()