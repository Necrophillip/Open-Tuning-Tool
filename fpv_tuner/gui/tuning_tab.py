import os
import shutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTextEdit, QSpinBox, QPushButton,
    QFileDialog, QGroupBox, QLabel, QMessageBox, QCheckBox, QDoubleSpinBox, QGridLayout,
    QComboBox
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg

from fpv_tuner.analysis.tuning import DRONE_PROFILES, parse_dump, tune_with_sliders, generate_cli, simulate_step_response, validate_settings, calculate_response_metrics, classify_step_response
from fpv_tuner.analysis.blackbox_parser import get_blackbox_headers
from fpv_tuner.blackbox.loader import _decode_blackbox_log

class TuningTab(QWidget):
    dump_filepath = None
    dump_version = None
    bb_log_path = None
    bb_log_version = None

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
        self._create_slider_display(left_panel_layout)
        self._create_simulation_controls(left_panel_layout)
        self._create_warning_display(left_panel_layout)
        left_panel_layout.addStretch()

        self._create_plot_controls(right_panel_layout)
        self._create_bottom_right_controls(right_panel_layout)
        self._connect_signals()

    def _create_load_controls(self, parent_layout):
        group = QGroupBox("1. Load Configuration")
        layout = QVBoxLayout(group)
        self.load_dump_button = QPushButton("Load Betaflight Dump File...")
        self.dump_file_label = QLabel("No file loaded.")
        self.load_bb_button = QPushButton("Load Blackbox CSV Log...")
        self.bb_file_label = QLabel("No file loaded.")
        self.version_status_label = QLabel("Versions: N/A")

        layout.addWidget(self.load_dump_button)
        layout.addWidget(self.dump_file_label)
        layout.addWidget(self.load_bb_button)
        layout.addWidget(self.bb_file_label)
        layout.addWidget(self.version_status_label)
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

    def _create_slider_display(self, parent_layout):
        group = QGroupBox("5. Proposed Sliders")
        layout = QFormLayout(group)
        self.slider_master = QLabel("1.0")
        self.slider_tracking = QLabel("1.0")
        self.slider_drift = QLabel("1.0")
        self.slider_damp = QLabel("1.0")
        self.slider_ff = QLabel("1.0")
        layout.addRow("Master:", self.slider_master)
        layout.addRow("Tracking:", self.slider_tracking)
        layout.addRow("Drift:", self.slider_drift)
        layout.addRow("Damping:", self.slider_damp)
        layout.addRow("FeedForward:", self.slider_ff)
        parent_layout.addWidget(group)

    def _create_simulation_controls(self, parent_layout):
        group = QGroupBox("6. Simulation Settings")
        layout = QFormLayout(group)
        self.noise_checkbox = QCheckBox("Enable Gyro Noise")
        self.noise_level_spinbox = QDoubleSpinBox()
        self.noise_level_spinbox.setRange(0.0, 1.0)
        self.noise_level_spinbox.setSingleStep(0.01)
        self.noise_level_spinbox.setValue(0.05)
        self.noise_level_spinbox.setEnabled(False)
        self.wind_gust_button = QPushButton("Simulate Wind Gust")
        self.duration_spinbox = QDoubleSpinBox()
        self.duration_spinbox.setRange(0.2, 5.0)
        self.duration_spinbox.setSingleStep(0.1)
        self.duration_spinbox.setValue(1.0)
        self.duration_spinbox.setSuffix(" s")

        layout.addRow(self.noise_checkbox)
        layout.addRow("Noise Level:", self.noise_level_spinbox)
        layout.addRow("Duration:", self.duration_spinbox)

        self.smoothing_slider = QSlider(Qt.Orientation.Horizontal)
        self.smoothing_slider.setRange(0, 20)
        self.smoothing_slider.setValue(0)
        self.smoothing_label = QLabel("Raw")
        smoothing_layout = QHBoxLayout()
        smoothing_layout.addWidget(self.smoothing_slider)
        smoothing_layout.addWidget(self.smoothing_label)
        layout.addRow("Plot Smoothing:", smoothing_layout)

        layout.addWidget(self.wind_gust_button)
        parent_layout.addWidget(group)

    def _create_warning_display(self, parent_layout):
        group = QGroupBox("7. Warnings")
        layout = QVBoxLayout(group)
        self.warning_text_area = QTextEdit()
        self.warning_text_area.setReadOnly(True)
        self.warning_text_area.setStyleSheet("QTextEdit { color: red; }")
        self.warning_text_area.setVisible(False) # Hide when no warnings
        layout.addWidget(self.warning_text_area)
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

        self.classification_current = QLabel("N/A")
        self.classification_proposed = QLabel("N/A")
        metrics_layout.addRow("Classification:", self._create_metric_row(self.classification_current, self.classification_proposed))

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
        self.load_bb_button.clicked.connect(self.on_load_blackbox)
        self.propose_button.clicked.connect(self.on_generate_proposal)
        self.update_simulation_button.clicked.connect(lambda: self.run_simulations_and_update_cli())
        self.wind_gust_button.clicked.connect(self.on_simulate_wind_gust)
        self.noise_checkbox.toggled.connect(self.noise_level_spinbox.setEnabled)

        for widget in self.pid_widgets.values():
            if isinstance(widget, QSpinBox):
                widget.valueChanged.connect(lambda: self.run_simulations_and_update_cli())

        self.noise_checkbox.toggled.connect(lambda: self.run_simulations_and_update_cli())
        self.noise_level_spinbox.valueChanged.connect(lambda: self.run_simulations_and_update_cli())
        self.duration_spinbox.valueChanged.connect(lambda: self.run_simulations_and_update_cli())
        self.axis_combo.currentTextChanged.connect(lambda: self.run_simulations_and_update_cli())
        self.profile_combo.currentTextChanged.connect(lambda: self.run_simulations_and_update_cli())
        self.smoothing_slider.valueChanged.connect(self.on_smoothing_label_changed)
        self.smoothing_slider.valueChanged.connect(lambda: self.run_simulations_and_update_cli())

    def on_smoothing_label_changed(self, value):
        if value == 0:
            self.smoothing_label.setText("Raw")
        else:
            self.smoothing_label.setText(f"Level {value}")

    def on_load_dump(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Betaflight Dump", "", "Text Files (*.txt);;All Files (*)")
        if not filepath: return

        backup_path = filepath + ".bak"
        if not os.path.exists(backup_path):
            try:
                shutil.copy2(filepath, backup_path)
            except Exception as e:
                QMessageBox.warning(self, "Backup Failed", f"Could not create a backup of the dump file.\n\n{e}")

        pids, version, error = parse_dump(filepath)
        if error:
            QMessageBox.critical(self, "Error Parsing Dump", error)
            return

        self.dump_filepath = filepath
        self.current_pids = pids
        self.dump_version = version
        self.dump_file_label.setText(os.path.basename(filepath))
        self.propose_button.setEnabled(True)
        self.update_ui_with_pids(self.current_pids, target='all')
        self.run_simulations_and_update_cli(is_initial_run=True)
        self._check_versions()

    def on_load_blackbox(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Blackbox Log", "", "Blackbox Logs (*.bbl *.bfl *.csv);;All Files (*)")
        if not filepath: return

        temp_dir = None
        # If it's a raw log, decode it first
        if os.path.splitext(filepath)[1].lower() in ['.bbl', '.bfl']:
            self.setCursor(Qt.CursorShape.WaitCursor)
            csv_path, temp_dir, error = _decode_blackbox_log(filepath)
            self.setCursor(Qt.CursorShape.ArrowCursor)

            if error:
                QMessageBox.critical(self, "Error Decoding Log", error)
                if temp_dir and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                return

            # The path we want to parse headers from is the new temp CSV
            path_to_parse = csv_path
        else:
            # It's already a CSV
            path_to_parse = filepath

        headers = get_blackbox_headers(path_to_parse)
        self.bb_log_version = headers.get("Firmware version")
        self.bb_log_path = filepath # Still store the original path
        self.bb_file_label.setText(os.path.basename(filepath))
        self._check_versions()

        # Clean up temporary directory if one was created
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _check_versions(self):
        if not self.dump_version and not self.bb_log_version:
            self.version_status_label.setText("Versions: N/A")
            return

        if self.dump_version and self.bb_log_version:
            if self.dump_version == self.bb_log_version:
                self.version_status_label.setText("Versions Match!")
                self.version_status_label.setStyleSheet("color: green;")
            else:
                self.version_status_label.setText("Versions Mismatch!")
                self.version_status_label.setStyleSheet("color: red;")
        else:
            self.version_status_label.setText("Versions: Waiting for other file...")
            self.version_status_label.setStyleSheet("")

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

        self.proposed_pids, sliders = tune_with_sliders(
            self.current_pids, drone_profile, axis_to_tune
        )

        self.setCursor(Qt.CursorShape.ArrowCursor)

        self.update_ui_with_pids(self.proposed_pids, target='proposed')
        self.update_slider_display(sliders)

        self.run_simulations_and_update_cli()
        self.update_simulation_button.setEnabled(True)

    def update_slider_display(self, sliders):
        self.slider_master.setText(f"{sliders.get('master', 1.0):.2f}")
        self.slider_tracking.setText(f"{sliders.get('tracking', 1.0):.2f}")
        self.slider_drift.setText(f"{sliders.get('drift', 1.0):.2f}")
        self.slider_damp.setText(f"{sliders.get('damp', 1.0):.2f}")
        self.slider_ff.setText(f"{sliders.get('ff', 1.0):.2f}")

    def on_simulate_wind_gust(self):
        self.run_simulations_and_update_cli(disturbance_magnitude=20.0, disturbance_time=0.1)

    def run_simulations_and_update_cli(self, is_initial_run=False, disturbance_magnitude=0.0, disturbance_time=0.0):
        if not self.current_pids: return
        self.plot_widget.clear()

        profile_name = self.profile_combo.currentText()
        drone_profile = DRONE_PROFILES.get(profile_name, DRONE_PROFILES["Default"])
        axis_to_simulate = self.axis_combo.currentText().lower()
        noise_level = self.noise_level_spinbox.value() if self.noise_checkbox.isChecked() else 0.0
        duration = self.duration_spinbox.value()
        inertia = drone_profile.get("inertia", 0.005)

        sim_before = simulate_step_response(self.current_pids, axis_to_simulate, inertia, duration=duration, noise_level=noise_level, disturbance_magnitude=disturbance_magnitude, disturbance_time=disturbance_time)
        if sim_before and sim_before.get("time") is not None:
            smoothing_level = self.smoothing_slider.value()
            response_smoothed = apply_smoothing(sim_before["response"], smoothing_level)
            self.plot_widget.plot(sim_before["time"], response_smoothed, pen='r', name='Current Response')
            metrics = calculate_response_metrics(sim_before["time"], sim_before["response"])
            self._update_metrics_display(metrics, is_current=True)
            self._update_classification_display(metrics, is_current=True)

        if is_initial_run: return

        self.proposed_pids = self.current_pids.copy()
        for axis in ["roll", "pitch", "yaw"]:
            for term in ["p", "i", "d"]:
                self.proposed_pids[f"{term}_{axis}"] = self.pid_widgets[f"proposed_{term}_{axis}"].value()

        sim_after = simulate_step_response(self.proposed_pids, axis_to_simulate, inertia, duration=duration, noise_level=noise_level, disturbance_magnitude=disturbance_magnitude, disturbance_time=disturbance_time)
        if sim_after and sim_after.get("time") is not None:
            smoothing_level = self.smoothing_slider.value()
            response_smoothed = apply_smoothing(sim_after["response"], smoothing_level)
            p_trace_smoothed = apply_smoothing(sim_after["p_trace"], smoothing_level)
            i_trace_smoothed = apply_smoothing(sim_after["i_trace"], smoothing_level)

            self.plot_widget.plot(sim_after["time"], response_smoothed, pen='g', name='Proposed Response')
            self.plot_widget.plot(sim_after["time"], p_trace_smoothed, pen={'color': (0, 100, 255, 150), 'style': Qt.PenStyle.DashLine}, name='P Term (Proposed)')
            self.plot_widget.plot(sim_after["time"], i_trace_smoothed, pen={'color': (255, 0, 255, 150), 'style': Qt.PenStyle.DashLine}, name='I Term (Proposed)')
            d_trace_smoothed = apply_smoothing(sim_after["d_trace"], smoothing_level)
            self.plot_widget.plot(sim_after["time"], d_trace_smoothed, pen={'color': (0, 255, 255, 150), 'style': Qt.PenStyle.DashLine}, name='D Term (Proposed)')

            metrics = calculate_response_metrics(sim_after["time"], sim_after["response"]) # Metrics on raw data
            self._update_metrics_display(metrics, is_current=False)
            self._update_classification_display(metrics, is_current=False)

        self.cli_output_text.setText(generate_cli(self.proposed_pids))

        # --- Validation ---
        warnings = validate_settings(self.proposed_pids, self.current_pids, drone_profile)
        if warnings:
            self.warning_text_area.setText("ATTENTION:\n" + "\n".join(warnings))
            self.warning_text_area.setVisible(True)
        else:
            self.warning_text_area.clear()
            self.warning_text_area.setVisible(False)

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

    def _update_classification_display(self, metrics, is_current=True):
        text, color = classify_step_response(metrics)
        label = self.classification_current if is_current else self.classification_proposed
        label.setText(text)
        label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def set_data(self, logs):
        pass
