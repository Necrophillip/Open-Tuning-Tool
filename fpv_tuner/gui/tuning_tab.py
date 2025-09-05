import os
import shutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTextEdit, QSpinBox, QPushButton,
    QFileDialog, QGroupBox, QLabel, QMessageBox, QCheckBox, QDoubleSpinBox, QGridLayout,
    QComboBox
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg

from fpv_tuner.analysis.tuning import DRONE_PROFILES, parse_dump, find_optimal_tune, generate_cli, simulate_step_response, validate_settings, calculate_response_metrics

class TuningTab(QWidget):
    dump_filepath = None
    current_pids = {}
    proposed_pids = {}

    def __init__(self):
        super().__init__()
        main_layout = QHBoxLayout(self)
        left_panel_layout = QVBoxLayout()
        right_panel_layout = QVBoxLayout()
        main_layout.addLayout(left_panel_layout, 2)
        main_layout.addLayout(right_panel_layout, 5)

        self._create_load_controls(left_panel_layout)
        self._create_scope_controls(left_panel_layout)
        self._create_pid_controls(left_panel_layout)
        self._create_simulation_controls(left_panel_layout)
        left_panel_layout.addStretch()

        self._create_plot_controls(right_panel_layout)
        self._create_bottom_right_controls(right_panel_layout)
        self._connect_signals()

    def _create_load_controls(self, parent_layout):
        group = QGroupBox("1. Load Configuration")
        layout = QVBoxLayout(group)
        self.load_dump_button = QPushButton("Load Betaflight Dump File...")
        self.dump_file_label = QLabel("No file loaded.")
        layout.addWidget(self.load_dump_button)
        layout.addWidget(self.dump_file_label)
        parent_layout.addWidget(group)

    def _create_scope_controls(self, parent_layout):
        group = QGroupBox("2. Tuning Scope")
        layout = QFormLayout(group)
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(DRONE_PROFILES.keys())
        self.axis_combo = QComboBox()
        self.axis_combo.addItems(["Roll", "Pitch", "Yaw"])
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["RP", "RPY"])
        layout.addRow("Drone Profile:", self.profile_combo)
        layout.addRow("Axis to Simulate:", self.axis_combo)
        layout.addRow("Axes to Tune:", self.mode_combo)
        parent_layout.addWidget(group)

    def _create_pid_controls(self, parent_layout):
        group = QGroupBox("3. PID Controller Settings")
        layout = QGridLayout(group)
        layout.addWidget(QLabel("<b>Current</b>"), 0, 1, 1, 3, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(QLabel("<b>Proposed</b>"), 0, 4, 1, 3, Qt.AlignmentFlag.AlignCenter)
        headers = ["Axis", "P", "I", "D", "P", "I", "D"]
        for i, header in enumerate(headers):
            layout.addWidget(QLabel(f"<b>{header}</b>"), 1, i)

        self.pid_widgets = {}
        for i, axis in enumerate(["Roll", "Pitch", "Yaw"]):
            row = i + 2
            layout.addWidget(QLabel(axis), row, 0)
            for j, term in enumerate(["p", "i", "d"]):
                current_key = f"current_{term}_{axis.lower()}"
                self.pid_widgets[current_key] = QLabel("N/A")
                layout.addWidget(self.pid_widgets[current_key], row, j + 1)
                proposed_key = f"proposed_{term}_{axis.lower()}"
                spinbox = QSpinBox()
                spinbox.setRange(0, 255)
                self.pid_widgets[proposed_key] = spinbox
                layout.addWidget(self.pid_widgets[proposed_key], row, j + 4)

        self.propose_button = QPushButton("Generate Proposal")
        self.propose_button.setEnabled(False)
        self.update_simulation_button = QPushButton("Update Simulation & CLI")
        self.update_simulation_button.setEnabled(False)
        layout.addWidget(self.propose_button, 5, 1, 1, 3)
        layout.addWidget(self.update_simulation_button, 5, 4, 1, 3)
        parent_layout.addWidget(group)

    def _create_simulation_controls(self, parent_layout):
        group = QGroupBox("4. Simulation Settings")
        layout = QFormLayout(group)
        self.noise_checkbox = QCheckBox("Enable Gyro Noise")
        self.noise_level_spinbox = QDoubleSpinBox()
        self.noise_level_spinbox.setRange(0.0, 1.0)
        self.noise_level_spinbox.setSingleStep(0.01)
        self.noise_level_spinbox.setValue(0.05)
        self.noise_level_spinbox.setEnabled(False)
        self.wind_gust_button = QPushButton("Simulate Wind Gust")
        layout.addRow(self.noise_checkbox)
        layout.addRow("Noise Level:", self.noise_level_spinbox)
        layout.addWidget(self.wind_gust_button)
        parent_layout.addWidget(group)

    def _create_plot_controls(self, parent_layout):
        self.plot_widget = pg.PlotWidget(title="Simulated Step Response")
        self.plot_widget.addLegend()
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.setLabel('left', 'Response / PID Output')
        self.plot_widget.showGrid(x=True, y=True)
        parent_layout.addWidget(self.plot_widget, 2)

    def _create_bottom_right_controls(self, parent_layout):
        bottom_layout = QHBoxLayout()
        metrics_group = QGroupBox("Performance Metrics")
        metrics_layout = QFormLayout(metrics_group)

        self.metrics_overshoot_current = QLabel("N/A")
        self.metrics_overshoot_proposed = QLabel("N/A")
        self.metrics_rise_time_current = QLabel("N/A")
        self.metrics_rise_time_proposed = QLabel("N/A")
        self.metrics_settling_time_current = QLabel("N/A")
        self.metrics_settling_time_proposed = QLabel("N/A")
        self.metrics_oscillation_current = QLabel("N/A")
        self.metrics_oscillation_proposed = QLabel("N/A")

        current_label = QLabel("<b>Current</b>")
        proposed_label = QLabel("<b>Proposed</b>")
        metrics_layout.addRow("", self._create_metric_row(current_label, proposed_label))
        metrics_layout.addRow("Overshoot (%):", self._create_metric_row(self.metrics_overshoot_current, self.metrics_overshoot_proposed))
        metrics_layout.addRow("Rise Time (s):", self._create_metric_row(self.metrics_rise_time_current, self.metrics_rise_time_proposed))
        metrics_layout.addRow("Settling Time (s):", self._create_metric_row(self.metrics_settling_time_current, self.metrics_settling_time_proposed))
        metrics_layout.addRow("Oscillation:", self._create_metric_row(self.metrics_oscillation_current, self.metrics_oscillation_proposed))

        bottom_layout.addWidget(metrics_group)
        cli_group = QGroupBox("CLI Commands")
        cli_layout = QVBoxLayout(cli_group)
        self.cli_output_text = QTextEdit()
        self.cli_output_text.setReadOnly(True)
        self.cli_output_text.setFontFamily("monospace")
        cli_layout.addWidget(self.cli_output_text)
        bottom_layout.addWidget(cli_group)
        parent_layout.addLayout(bottom_layout, 1)

    def _create_metric_row(self, label1, label2):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.addWidget(label1)
        layout.addWidget(label2)
        layout.setContentsMargins(0,0,0,0)
        return widget

    def _connect_signals(self):
        self.load_dump_button.clicked.connect(self.on_load_dump)
        self.propose_button.clicked.connect(self.on_generate_proposal)
        self.update_simulation_button.clicked.connect(lambda: self.run_simulations_and_update_cli())
        self.wind_gust_button.clicked.connect(self.on_simulate_wind_gust)
        self.noise_checkbox.toggled.connect(self.noise_level_spinbox.setEnabled)

        for widget in self.pid_widgets.values():
            if isinstance(widget, QSpinBox):
                widget.valueChanged.connect(lambda: self.run_simulations_and_update_cli())

        self.noise_checkbox.toggled.connect(lambda: self.run_simulations_and_update_cli())
        self.noise_level_spinbox.valueChanged.connect(lambda: self.run_simulations_and_update_cli())
        self.axis_combo.currentTextChanged.connect(lambda: self.run_simulations_and_update_cli())
        self.profile_combo.currentTextChanged.connect(lambda: self.run_simulations_and_update_cli())

    def on_load_dump(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Betaflight Dump", "", "Text Files (*.txt);;All Files (*)")
        if not filepath: return

        backup_path = filepath + ".bak"
        if not os.path.exists(backup_path):
            try:
                shutil.copy2(filepath, backup_path)
            except Exception as e:
                QMessageBox.warning(self, "Backup Failed", f"Could not create a backup of the dump file.\n\n{e}")

        pids, error = parse_dump(filepath)
        if error:
            QMessageBox.critical(self, "Error Parsing Dump", error)
            return

        self.dump_filepath = filepath
        self.current_pids = pids
        self.dump_file_label.setText(os.path.basename(filepath))
        self.propose_button.setEnabled(True)
        self.update_ui_with_pids(self.current_pids, target='all')
        self.run_simulations_and_update_cli(is_initial_run=True)

    def update_ui_with_pids(self, pids, target='all'):
        for axis in ["roll", "pitch", "yaw"]:
            for term in ["p", "i", "d"]:
                pid_key = f"{term}_{axis}"
                if target in ['all', 'current']:
                    widget_key = f"current_{pid_key}"
                    self.pid_widgets[widget_key].setText(str(pids.get(pid_key, "N/A")))
                if target in ['all', 'proposed']:
                    widget_key = f"proposed_{pid_key}"
                    self.pid_widgets[widget_key].setValue(pids.get(pid_key, 0))

    def on_generate_proposal(self):
        if not self.current_pids: return

        self.setCursor(Qt.CursorShape.WaitCursor)
        profile_name = self.profile_combo.currentText()
        drone_profile = DRONE_PROFILES.get(profile_name, DRONE_PROFILES["Default"])
        axis_to_tune = self.axis_combo.currentText().lower()
        tuning_mode = self.mode_combo.currentText()

        self.proposed_pids = find_optimal_tune(self.current_pids, drone_profile, axis_to_tune, tuning_mode)

        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update_ui_with_pids(self.proposed_pids, target='proposed')
        self.run_simulations_and_update_cli()
        self.update_simulation_button.setEnabled(True)

    def on_simulate_wind_gust(self):
        self.run_simulations_and_update_cli(disturbance_magnitude=20.0, disturbance_time=0.1)

    def run_simulations_and_update_cli(self, is_initial_run=False, disturbance_magnitude=0.0, disturbance_time=0.0):
        if not self.current_pids: return
        self.plot_widget.clear()

        profile_name = self.profile_combo.currentText()
        drone_profile = DRONE_PROFILES.get(profile_name, DRONE_PROFILES["Default"])
        axis_to_simulate = self.axis_combo.currentText().lower()
        noise_level = self.noise_level_spinbox.value() if self.noise_checkbox.isChecked() else 0.0
        inertia = drone_profile.get("inertia", 0.005)

        sim_before = simulate_step_response(self.current_pids, axis_to_simulate, inertia, noise_level=noise_level, disturbance_magnitude=disturbance_magnitude, disturbance_time=disturbance_time)
        if sim_before and sim_before.get("time") is not None:
            self.plot_widget.plot(sim_before["time"], sim_before["response"], pen='r', name='Current Response')
            self._update_metrics_display(calculate_response_metrics(sim_before["time"], sim_before["response"]), is_current=True)

        if is_initial_run: return

        self.proposed_pids = self.current_pids.copy()
        for axis in ["roll", "pitch", "yaw"]:
            for term in ["p", "i", "d"]:
                self.proposed_pids[f"{term}_{axis}"] = self.pid_widgets[f"proposed_{term}_{axis}"].value()

        sim_after = simulate_step_response(self.proposed_pids, axis_to_simulate, inertia, noise_level=noise_level, disturbance_magnitude=disturbance_magnitude, disturbance_time=disturbance_time)
        if sim_after and sim_after.get("time") is not None:
            self.plot_widget.plot(sim_after["time"], sim_after["response"], pen='g', name='Proposed Response')
            self.plot_widget.plot(sim_after["time"], sim_after["p_trace"], pen={'color': (0, 100, 255, 150), 'style': Qt.PenStyle.DashLine}, name='P Term (Proposed)')
            self.plot_widget.plot(sim_after["time"], sim_after["i_trace"], pen={'color': (255, 0, 255, 150), 'style': Qt.PenStyle.DashLine}, name='I Term (Proposed)')
            self.plot_widget.plot(sim_after["time"], sim_after["d_trace"], pen={'color': (0, 255, 255, 150), 'style': Qt.PenStyle.DashLine}, name='D Term (Proposed)')
            self._update_metrics_display(calculate_response_metrics(sim_after["time"], sim_after["response"]), is_current=False)

        self.cli_output_text.setText(generate_cli(self.proposed_pids))
        warnings = validate_settings(self.proposed_pids, drone_profile)
        if warnings:
            QMessageBox.warning(self, "Safety Warning", "The following proposed values are outside of the recommended safe ranges:\n\n" + "\n".join(warnings))

    def _update_metrics_display(self, metrics, is_current=True):
        if is_current:
            self.metrics_overshoot_current.setText(f"{metrics.get('Overshoot (%)', 0):.2f}")
            self.metrics_rise_time_current.setText(f"{metrics.get('Rise Time (s)', 0):.4f}")
            self.metrics_settling_time_current.setText(f"{metrics.get('Settling Time (s)', 0):.4f}")
            self.metrics_oscillation_current.setText(f"{metrics.get('Oscillation', 0):.2f}")
        else:
            self.metrics_overshoot_proposed.setText(f"{metrics.get('Overshoot (%)', 0):.2f}")
            self.metrics_rise_time_proposed.setText(f"{metrics.get('Rise Time (s)', 0):.4f}")
            self.metrics_settling_time_proposed.setText(f"{metrics.get('Settling Time (s)', 0):.4f}")
            self.metrics_oscillation_proposed.setText(f"{metrics.get('Oscillation', 0):.2f}")

    def set_data(self, logs):
        pass
