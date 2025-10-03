import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton,
    QFileDialog, QGroupBox, QLabel, QMessageBox, QComboBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QStackedWidget, QGridLayout
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg
import numpy as np

from fpv_tuner.analysis.tuning import (
    get_step_response, calculate_response_metrics, classify_step_response,
    suggest_pid_changes, generate_cli, DRONE_PROFILES, simulate_step_response
)
from fpv_tuner.blackbox.loader import load_log
from fpv_tuner.analysis.blackbox_parser import parse_pid_data_from_headers
from fpv_tuner.analysis.cli_parser import parse_pids_from_cli
from fpv_tuner.gui.suggestion_dialog import SuggestionDialog


class TuningTab(QWidget):
    plot_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

    def __init__(self):
        super().__init__()
        # Data storage
        self.loaded_logs = {}
        self.cli_pids = {}
        self.cli_filepath = None
        self.selected_bbl_path = None

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
        group = QGroupBox("1. Load Configuration")
        layout = QFormLayout(group)

        # BBL File Selection
        self.bbl_combo = QComboBox()
        self.bbl_combo.setToolTip("Select a loaded Blackbox log for step-response analysis.")

        # CLI File Loading
        self.load_cli_button = QPushButton("Load CLI Dump...")
        self.load_cli_button.setToolTip("Load a CLI dump to use its PID values as a baseline.")
        self.load_cli_button.setFixedSize(self.load_cli_button.sizeHint().width(), self.bbl_combo.sizeHint().height())

        self.loaded_bbl_label = QLabel("<font color='grey'><i>None</i></font>")
        self.loaded_cli_label = QLabel("<font color='grey'><i>None</i></font>")

        bbl_layout = QHBoxLayout()
        bbl_layout.addWidget(self.bbl_combo, 1)

        cli_layout = QHBoxLayout()
        cli_layout.addWidget(self.load_cli_button)
        cli_layout.addWidget(self.loaded_cli_label, 1, Qt.AlignmentFlag.AlignLeft)

        layout.addRow("Blackbox Log:", bbl_layout)
        layout.addRow("Loaded BBL:", self.loaded_bbl_label)
        layout.addRow("CLI Values:", cli_layout)

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
        self.single_plot_widget = pg.PlotWidget(title="Step Response Comparison")
        self.single_plot_widget.addLegend()
        self.single_plot_widget.setLabel('bottom', 'Time (s)')
        self.single_plot_widget.setLabel('left', 'Normalized Response')
        self.single_plot_widget.showGrid(x=True, y=True)
        self.reference_line = pg.InfiniteLine(pos=1.0, angle=0, movable=False, pen={'color': 'w', 'style': Qt.PenStyle.DashLine})
        self.single_plot_widget.addItem(self.reference_line)
        self.plot_stack.addWidget(self.single_plot_widget)
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
        self.load_cli_button.clicked.connect(self.on_load_cli)
        self.bbl_combo.currentTextChanged.connect(self.on_bbl_selection_changed)
        self.toggle_view_button.clicked.connect(self.toggle_view)
        self.axis_combo.currentTextChanged.connect(self.analyze_and_plot)
        self.profile_combo.currentTextChanged.connect(self.analyze_and_plot)
        self.suggest_button.clicked.connect(self.on_suggest_tune)

    def on_suggest_tune(self):
        # Determine the scenario based on loaded data
        bbl_selected = bool(self.selected_bbl_path)
        cli_loaded = bool(self.cli_pids)

        if not bbl_selected and not cli_loaded:
            QMessageBox.warning(self, "No Data", "Please select a Blackbox log or load a CLI dump to get a tuning suggestion.")
            return

        axis = self.axis_combo.currentText().lower()
        profile_name = self.profile_combo.currentText()
        drone_profile = DRONE_PROFILES.get(profile_name, DRONE_PROFILES["Default"])
        inertia = drone_profile.get("inertia", 0.005)

        current_pids = {}
        real_analysis = None

        # Scenario 1: BBL + CLI (CLI is the authority for PIDs)
        if bbl_selected and cli_loaded:
            current_pids = self.cli_pids
            log_data = self.loaded_logs[self.selected_bbl_path]
            real_analysis = get_step_response(log_data['df'].copy(), axis)
            if not real_analysis:
                QMessageBox.warning(self, "Analysis Failed", f"Could not extract a step response from {os.path.basename(self.selected_bbl_path)} for the {axis.capitalize()} axis.")
                return

        # Scenario 2: BBL Only
        elif bbl_selected:
            log_data = self.loaded_logs[self.selected_bbl_path]
            current_pids = log_data.get('pids', {})
            if not current_pids:
                QMessageBox.warning(self, "No PIDs", f"Could not find PID data in the header of {os.path.basename(self.selected_bbl_path)}.")
                return
            real_analysis = get_step_response(log_data['df'].copy(), axis)
            if not real_analysis:
                QMessageBox.warning(self, "Analysis Failed", f"Could not extract a step response from {os.path.basename(self.selected_bbl_path)} for the {axis.capitalize()} axis.")
                return

        # Scenario 3: CLI Only
        elif cli_loaded:
            current_pids = self.cli_pids
            # No real analysis possible, suggestion will be based on profile presets
            QMessageBox.information(self, "CLI Mode", "Suggesting tune based on CLI values and selected profile. No step response data available.")

        # --- Generate Suggestion ---
        if real_analysis:
            real_time, real_response_raw, setpoint = real_analysis["time"], real_analysis["response"], real_analysis["setpoint"]
            real_response_normalized = real_response_raw / setpoint
            metrics = calculate_response_metrics(real_time, real_response_normalized, setpoint=1.0)
            suggested_pids = suggest_pid_changes(current_pids, metrics, axis)
            real_data = {"time": real_time, "response": real_response_normalized}
        else: # CLI-only case
            # Create "dummy" metrics that represent a baseline tune for the profile
            # This will cause suggest_pid_changes to propose a standard tune.
            metrics = {'Overshoot (%)': 10, 'Rise Time (s)': 0.1, 'Settling Time (s)': 0.3}
            suggested_pids = suggest_pid_changes(current_pids, metrics, axis, is_cli_only=True)
            real_data = None

        # --- Simulate and Show Dialog ---
        suggested_time, suggested_response_normalized = simulate_step_response(suggested_pids, axis, inertia)
        cli_commands = generate_cli(suggested_pids, axis)

        suggested_data = {"time": suggested_time, "response": suggested_response_normalized}

        dialog = SuggestionDialog(current_pids, suggested_pids, axis, cli_commands, real_data, suggested_data, self)
        dialog.exec()

    def toggle_view(self):
        # This function is now less relevant for this tab's primary purpose
        # but kept for structural consistency if single/multi view is desired later.
        current_index = self.plot_stack.currentIndex()
        if current_index == 0:
            self.plot_stack.setCurrentIndex(1)
            self.toggle_view_button.setText("Switch to Single-View")
            self.axis_combo.setVisible(False)
        else:
            self.plot_stack.setCurrentIndex(0)
            self.toggle_view_button.setText("Switch to Multi-View")
            self.axis_combo.setVisible(True)
        self.analyze_and_plot()

    def on_load_cli(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open CLI Dump", "", "Text Files (*.txt);;All Files (*)")
        if not filepath:
            return

        try:
            with open(filepath, 'r') as f:
                content = f.read()

            pids = parse_pids_from_cli(content)
            if not pids:
                raise ValueError("No valid 'set' commands for PIDs found.")

            self.cli_pids = pids
            self.cli_filepath = filepath
            self.loaded_cli_label.setText(f"<font color='white'>{os.path.basename(filepath)}</font>")
            QMessageBox.information(self, "CLI Loaded", f"Successfully parsed PIDs for {', '.join(pids.keys())} axes.")

        except Exception as e:
            self.cli_pids = {}
            self.cli_filepath = None
            self.loaded_cli_label.setText("<font color='red'><i>Load failed</i></font>")
            QMessageBox.critical(self, "Error", f"Failed to parse CLI file:\n{e}")

    def on_bbl_selection_changed(self, text):
        if text == "None":
            self.selected_bbl_path = None
            self.loaded_bbl_label.setText("<font color='grey'><i>None</i></font>")
        else:
            # Find the full path from the filename
            for path in self.loaded_logs.keys():
                if os.path.basename(path) == text:
                    self.selected_bbl_path = path
                    self.loaded_bbl_label.setText(f"<font color='white'>{text}</font>")
                    break
        self.analyze_and_plot()


    def analyze_and_plot(self):
        if self.plot_stack.currentIndex() == 0:
            self._analyze_and_plot_single()
        else:
            self._analyze_and_plot_multi()

    def _analyze_and_plot_single(self):
        plot_widget = self.single_plot_widget
        plot_widget.clear()
        plot_widget.addItem(self.reference_line)

        if not self.selected_bbl_path:
            self.clear_display()
            text_item = pg.TextItem("Select a Blackbox log to see its step response.", anchor=(0.5, 0.5))
            plot_widget.addItem(text_item)
            return

        axis_to_analyze = self.axis_combo.currentText().lower()
        log_data = self.loaded_logs.get(self.selected_bbl_path)

        if not log_data or log_data.get('df') is None:
            self.clear_display()
            return

        filename = os.path.basename(self.selected_bbl_path)
        analysis_results = get_step_response(log_data['df'].copy(), axis_to_analyze)

        if analysis_results:
            time, response, setpoint = analysis_results["time"], analysis_results["response"], analysis_results["setpoint"]
            normalized_response = response / setpoint
            plot_name = f"{filename} (Setpoint: {setpoint:.0f} d/s)"
            plot_widget.plot(time, normalized_response, pen={'color': self.plot_colors[0], 'width': 2}, name=plot_name)

            metrics = calculate_response_metrics(time, normalized_response, setpoint=1.0)
            metrics['filename'] = filename
            self._update_metrics_table([metrics])

            settling_time = metrics.get('Settling Time (s)', 0)
            max_settling_time = 0.4 if np.isnan(settling_time) else settling_time
            plot_widget.setXRange(-0.05, max_settling_time * 1.1, padding=0)
            plot_widget.setYRange(-0.2, 1.8, padding=0)
        else:
            self.clear_display()
            text_item = pg.TextItem(f"Could not extract step response for '{axis_to_analyze.capitalize()}' axis from {filename}.", anchor=(0.5, 0.5))
            plot_widget.addItem(text_item)


    def _analyze_and_plot_multi(self):
        # This view is less critical now but maintained for consistency
        self.metrics_table.setRowCount(0)
        if not self.selected_bbl_path:
            for axis, plot_widget in self.multi_plot_widgets.items():
                plot_widget.clear()
                plot_widget.addItem(pg.TextItem("Select a Blackbox log.", anchor=(0.5, 0.5)))
            return

        log_data = self.loaded_logs.get(self.selected_bbl_path)
        if not log_data: return

        filename = os.path.basename(self.selected_bbl_path)
        color = self.plot_colors[0]

        for axis, plot_widget in self.multi_plot_widgets.items():
            plot_widget.clear()
            analysis_results = get_step_response(log_data['df'].copy(), axis)
            if analysis_results:
                time, response, setpoint = analysis_results["time"], analysis_results["response"], analysis_results["setpoint"]
                plot_widget.plot(time, response, pen={'color': color, 'width': 2}, name=filename)
                ref_line = pg.InfiniteLine(pos=setpoint, angle=0, movable=False, pen={'color': color, 'style': Qt.PenStyle.DashLine})
                plot_widget.addItem(ref_line)
            else:
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
        self.single_plot_widget.clear()
        self.single_plot_widget.addItem(self.reference_line)
        self.metrics_table.setRowCount(0)

    def set_data(self, logs):
        self.loaded_logs = logs

        current_selection = self.bbl_combo.currentText()
        self.bbl_combo.blockSignals(True)
        self.bbl_combo.clear()

        self.bbl_combo.addItem("None")
        filenames = [os.path.basename(p) for p in self.loaded_logs.keys()]
        self.bbl_combo.addItems(filenames)

        # Restore previous selection if it still exists
        if current_selection in filenames:
            self.bbl_combo.setCurrentText(current_selection)
        else:
            self.bbl_combo.setCurrentIndex(0) # "None"
            self.on_bbl_selection_changed("None") # Manually trigger update

        self.bbl_combo.blockSignals(False)

        # If the previously selected item is no longer in the list, this will trigger the "None" case
        if self.bbl_combo.currentText() != current_selection:
            self.on_bbl_selection_changed(self.bbl_combo.currentText())

        self.analyze_and_plot()