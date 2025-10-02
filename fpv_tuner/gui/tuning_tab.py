import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton,
    QFileDialog, QGroupBox, QLabel, QMessageBox, QComboBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg
import numpy as np

from fpv_tuner.analysis.tuning import get_step_response, calculate_response_metrics, classify_step_response, suggest_pid_changes
from fpv_tuner.blackbox.loader import load_log
from fpv_tuner.analysis.blackbox_parser import get_blackbox_headers, parse_pid_data_from_headers
from fpv_tuner.gui.suggestion_dialog import SuggestionDialog

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
        self._create_suggestion_controls(left_panel_layout)
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
        self.scope_group = QGroupBox("2. Analysis Scope")
        layout = QFormLayout(self.scope_group)

        self.profile_combo = QComboBox()
        self.profile_combo.addItems(DRONE_PROFILES.keys())
        layout.addRow("Drone Profile:", self.profile_combo)

        self.axis_combo = QComboBox()
        self.axis_combo.addItems(["Roll", "Pitch", "Yaw"])
        layout.addRow("Axis:", self.axis_combo)

        self.toggle_view_button = QPushButton("Switch to Multi-View")
        layout.addRow(self.toggle_view_button)

        parent_layout.addWidget(self.scope_group)

    def _create_plot_controls(self, parent_layout):
        self.plot_stack = QStackedWidget()

        # --- Single Plot View ---
        self.single_plot_widget = pg.PlotWidget(title="Step Response Comparison")
        self.single_plot_widget.addLegend()
        self.single_plot_widget.setLabel('bottom', 'Time (s)')
        self.single_plot_widget.setLabel('left', 'Normalized Response')
        self.single_plot_widget.showGrid(x=True, y=True)
        self.reference_line = pg.InfiniteLine(pos=1.0, angle=0, movable=False, pen={'color': 'w', 'style': Qt.PenStyle.DashLine})
        self.single_plot_widget.addItem(self.reference_line)
        self.plot_stack.addWidget(self.single_plot_widget)

        # --- Multi Plot View ---
        multi_plot_container = QWidget()
        multi_layout = QGridLayout(multi_plot_container)
        self.multi_plot_widgets = {}
        for i, axis in enumerate(["Roll", "Pitch", "Yaw"]):
            plot = pg.PlotWidget(title=f"{axis} Step Response")
            plot.addLegend()
            plot.setLabel('bottom', 'Time (s)')
            plot.setLabel('left', 'deg/s')
            plot.showGrid(x=True, y=True)
            self.multi_plot_widgets[axis.lower()] = plot
            multi_layout.addWidget(plot, i, 0)
        self.plot_stack.addWidget(multi_plot_container)

        parent_layout.addWidget(self.plot_stack, 2)

    def _create_metrics_display(self, parent_layout):
        group = QGroupBox("Performance Metrics")
        layout = QVBoxLayout(group)
        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(5)
        self.metrics_table.setHorizontalHeaderLabels(["File", "Overshoot (%)", "Rise Time (s)", "Settling Time (s)", "Classification"])
        self.metrics_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.metrics_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.metrics_table.verticalHeader().setVisible(False)
        self.metrics_table.setMaximumHeight(150)
        layout.addWidget(self.metrics_table)
        parent_layout.addWidget(group)

    def _create_suggestion_controls(self, parent_layout):
        group = QGroupBox("3. Tuning Suggestions")
        layout = QVBoxLayout(group)
        self.suggest_button = QPushButton("Suggest Tune...")
        self.suggest_button.setToolTip("Analyze the response of the first log and suggest PID changes.")
        layout.addWidget(self.suggest_button)
        parent_layout.addWidget(group)

    def _connect_signals(self):
        self.load_bb_button.clicked.connect(self.on_load_blackbox)
        self.clear_logs_button.clicked.connect(self.on_clear_logs)
        self.toggle_view_button.clicked.connect(self.toggle_view)
        self.axis_combo.currentTextChanged.connect(self.analyze_and_plot)
        self.profile_combo.currentTextChanged.connect(self.analyze_and_plot)
        self.suggest_button.clicked.connect(self.on_suggest_tune)

    def on_suggest_tune(self):
        if not self.loaded_logs:
            QMessageBox.warning(self, "No Logs", "Please load a Blackbox log first.")
            return

        first_log_path = next(iter(self.loaded_logs))
        log_data = self.loaded_logs[first_log_path]

        current_pids = log_data.get('pids', {})
        if not current_pids:
            QMessageBox.warning(self, "No PIDs", f"Could not find PID data in the header of {os.path.basename(first_log_path)}.")
            return

        axis = self.axis_combo.currentText().lower()

        # 1. Get real response data
        real_analysis = get_step_response(log_data['df'].copy(), axis)
        if not real_analysis:
            QMessageBox.warning(self, "Analysis Failed", "Could not extract a step response to base a suggestion on.")
            return

        real_time, real_response_raw, setpoint = real_analysis["time"], real_analysis["response"], real_analysis["setpoint"]
        real_response_normalized = real_response_raw / setpoint

        # 2. Get metrics and suggested PIDs
        metrics = calculate_response_metrics(real_time, real_response_normalized, setpoint=1.0)
        suggested_pids = suggest_pid_changes(current_pids, metrics, axis)

        # 3. Simulate suggested response
        from fpv_tuner.analysis.tuning import DRONE_PROFILES, simulate_step_response, generate_cli
        profile_name = self.profile_combo.currentText() # Assumes a profile combo exists
        drone_profile = DRONE_PROFILES.get(profile_name, DRONE_PROFILES["Default"])
        inertia = drone_profile.get("inertia", 0.005)

        suggested_time, suggested_response_normalized = simulate_step_response(suggested_pids, axis, inertia)

        # 4. Show dialog
        cli_commands = generate_cli(suggested_pids, axis)

        real_data = {"time": real_time, "response": real_response_normalized}
        suggested_data = {"time": suggested_time, "response": suggested_response_normalized}

        dialog = SuggestionDialog(current_pids, suggested_pids, axis, cli_commands, real_data, suggested_data, self)
        dialog.exec()

    def toggle_view(self):
        current_index = self.plot_stack.currentIndex()
        if current_index == 0:
            self.plot_stack.setCurrentIndex(1)
            self.toggle_view_button.setText("Switch to Single-View")
            self.axis_combo.setVisible(False)
        else:
            self.plot_stack.setCurrentIndex(0)
            self.toggle_view_button.setText("Switch to Multi-View")
            self.axis_combo.setVisible(True)
        self.analyze_and_plot() # Re-plot on view change

    def on_load_blackbox(self):
        filepaths, _ = QFileDialog.getOpenFileNames(self, "Open Blackbox Log(s)", "", "Blackbox Logs (*.bbl *.bfl *.csv);;All Files (*)")
        if not filepaths:
            return

        for path in filepaths:
            if path in self.loaded_logs:
                continue

            self.setCursor(Qt.CursorShape.WaitCursor)
            df, pids, error = load_log(path)
            self.setCursor(Qt.CursorShape.ArrowCursor)

            if error:
                QMessageBox.critical(self, "Error Loading Log", f"Failed to load {os.path.basename(path)}:\n{error}")
                continue

            self.loaded_logs[path] = {'df': df, 'pids': pids}

        self._update_loaded_files_label()
        self.analyze_and_plot()

    def on_clear_logs(self):
        self.loaded_logs.clear()
        self._update_loaded_files_label()
        self.clear_display()

    def analyze_and_plot(self):
        if self.plot_stack.currentIndex() == 0:
            self._analyze_and_plot_single()
        else:
            self._analyze_and_plot_multi()

    def _analyze_and_plot_single(self):
        plot_widget = self.single_plot_widget
        plot_widget.clear()
        plot_widget.addItem(self.reference_line)

        if not self.loaded_logs:
            self.clear_display()
            return

        axis_to_analyze = self.axis_combo.currentText().lower()
        all_metrics_data = []
        max_settling_time = 0.4

        for i, (path, log_data) in enumerate(self.loaded_logs.items()):
            color = self.plot_colors[i % len(self.plot_colors)]
            filename = os.path.basename(path)

            # Extract the dataframe from the loaded data structure
            df = log_data.get('df')
            if df is None:
                print(f"Error: No dataframe found for {filename}")
                continue

            analysis_results = get_step_response(df.copy(), axis_to_analyze)

            if analysis_results:
                time, response, setpoint = analysis_results["time"], analysis_results["response"], analysis_results["setpoint"]
                normalized_response = response / setpoint
                plot_name = f"{filename} (Setpoint: {setpoint:.0f} d/s)"
                plot_widget.plot(time, normalized_response, pen={'color': color, 'width': 2}, name=plot_name)

                metrics = calculate_response_metrics(time, normalized_response, setpoint=1.0)
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
            plot_widget.addItem(text_item)
        else:
            plot_widget.setXRange(-0.05, max_settling_time * 1.1, padding=0)
            plot_widget.setYRange(-0.2, 1.8, padding=0)

    def _analyze_and_plot_multi(self):
        # In multi-view, we don't show the metrics table for simplicity
        self.metrics_table.setRowCount(0)

        for axis, plot_widget in self.multi_plot_widgets.items():
            plot_widget.clear()

            if not self.loaded_logs:
                plot_widget.addItem(pg.TextItem("No logs loaded.", anchor=(0.5, 0.5)))
                continue

            has_data_for_axis = False
            for i, (path, log_data) in enumerate(self.loaded_logs.items()):
                color = self.plot_colors[i % len(self.plot_colors)]
                filename = os.path.basename(path)

                # Extract the dataframe from the loaded data structure
                df = log_data.get('df')
                if df is None:
                    print(f"Error: No dataframe found for {filename}")
                    continue

                analysis_results = get_step_response(df.copy(), axis)

                if analysis_results:
                    has_data_for_axis = True
                    time = analysis_results.get("time")
                    response = analysis_results.get("response")
                    setpoint = analysis_results.get("setpoint")

                    if time is not None and response is not None and setpoint is not None:
                        # Plot raw response and dynamic setpoint line
                        plot_widget.plot(time, response, pen={'color': color, 'width': 2}, name=filename)
                        ref_line = pg.InfiniteLine(pos=setpoint, angle=0, movable=False, pen={'color': color, 'style': Qt.PenStyle.DashLine})
                        plot_widget.addItem(ref_line)

            if not has_data_for_axis:
                 plot_widget.addItem(pg.TextItem(f"No step response found for this axis.", anchor=(0.5, 0.5)))

    def _update_metrics_table(self, metrics_data):
        self.metrics_table.setRowCount(len(metrics_data))
        for row, data in enumerate(metrics_data):
            classification_text, _ = classify_step_response(data)
            self.metrics_table.setItem(row, 0, QTableWidgetItem(data.get('filename', 'N/A')))
            self.metrics_table.setItem(row, 1, QTableWidgetItem(f"{data.get('Overshoot (%)', 0):.2f}"))
            self.metrics_table.setItem(row, 2, QTableWidgetItem(f"{data.get('Rise Time (s)', 0):.4f}"))
            self.metrics_table.setItem(row, 3, QTableWidgetItem(f"{data.get('Settling Time (s)', 0):.4f}"))
            self.metrics_table.setItem(row, 4, QTableWidgetItem(classification_text))

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