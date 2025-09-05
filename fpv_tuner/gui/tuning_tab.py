import os
import shutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTextEdit, QSpinBox, QPushButton,
    QFileDialog, QGroupBox, QLabel, QMessageBox, QCheckBox, QDoubleSpinBox
)
from PyQt6.QtCore import pyqtSignal
import pyqtgraph as pg

# Import backend logic
from fpv_tuner.analysis.tuning import parse_dump, find_optimal_tune, generate_cli, simulate_step_response, validate_settings, calculate_response_metrics

class TuningTab(QWidget):
    # Store data
    dump_filepath = None
    current_pids = {}
    proposed_pids = {}

    def __init__(self):
        super().__init__()

        # --- Main Layout ---
        main_layout = QHBoxLayout(self)

        # --- Left Panel (Controls) ---
        left_panel_layout = QVBoxLayout()
        main_layout.addLayout(left_panel_layout, 1)

        # --- Right Panel (Plot and CLI) ---
        right_panel_layout = QVBoxLayout()
        main_layout.addLayout(right_panel_layout, 3)

        # --- Left Panel Widgets ---
        load_group = QGroupBox("1. Load Configuration")
        load_layout = QVBoxLayout(load_group)
        self.load_dump_button = QPushButton("Load Betaflight Dump File...")
        self.dump_file_label = QLabel("No file loaded.")
        load_layout.addWidget(self.load_dump_button)
        load_layout.addWidget(self.dump_file_label)
        left_panel_layout.addWidget(load_group)

        current_pids_group = QGroupBox("2. Current PID Values")
        current_pids_layout = QFormLayout(current_pids_group)
        self.current_p_roll = QLabel("N/A")
        self.current_i_roll = QLabel("N/A")
        self.current_d_roll = QLabel("N/A")
        self.current_p_pitch = QLabel("N/A")
        self.current_i_pitch = QLabel("N/A")
        self.current_d_pitch = QLabel("N/A")
        current_pids_layout.addRow("Roll P:", self.current_p_roll)
        current_pids_layout.addRow("Roll I:", self.current_i_roll)
        current_pids_layout.addRow("Roll D:", self.current_d_roll)
        current_pids_layout.addRow("Pitch P:", self.current_p_pitch)
        current_pids_layout.addRow("Pitch I:", self.current_i_pitch)
        current_pids_layout.addRow("Pitch D:", self.current_d_pitch)
        left_panel_layout.addWidget(current_pids_group)

        proposed_pids_group = QGroupBox("3. Propose & Modify Tune")
        proposed_pids_layout = QFormLayout(proposed_pids_group)
        self.propose_button = QPushButton("Generate Proposal")
        self.propose_button.setEnabled(False)
        self.update_simulation_button = QPushButton("Update Simulation & CLI")
        self.update_simulation_button.setEnabled(False)

        self.proposed_d_roll = QSpinBox()
        self.proposed_d_pitch = QSpinBox()
        self.proposed_d_roll.setRange(0, 200)
        self.proposed_d_pitch.setRange(0, 200)

        proposed_pids_layout.addWidget(self.propose_button)
        proposed_pids_layout.addRow("New Roll D:", self.proposed_d_roll)
        proposed_pids_layout.addRow("New Pitch D:", self.proposed_d_pitch)
        proposed_pids_layout.addWidget(self.update_simulation_button)
        left_panel_layout.addWidget(proposed_pids_group)

        # Simulation Settings Box
        sim_settings_group = QGroupBox("Simulation Settings")
        sim_settings_layout = QFormLayout(sim_settings_group)
        self.noise_checkbox = QCheckBox("Enable Gyro Noise")
        self.noise_level_spinbox = QDoubleSpinBox()
        self.noise_level_spinbox.setRange(0.0, 1.0)
        self.noise_level_spinbox.setSingleStep(0.01)
        self.noise_level_spinbox.setValue(0.05)
        self.noise_level_spinbox.setEnabled(False) # Disabled by default

        sim_settings_layout.addRow(self.noise_checkbox)
        sim_settings_layout.addRow("Noise Level:", self.noise_level_spinbox)
        self.wind_gust_button = QPushButton("Simulate Wind Gust")
        sim_settings_layout.addWidget(self.wind_gust_button)
        left_panel_layout.addWidget(sim_settings_group)

        left_panel_layout.addStretch()

        # --- Right Panel Widgets ---
        self.plot_widget = pg.PlotWidget(title="Simulated Step Response")
        self.plot_widget.addLegend()
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.setLabel('left', 'Response')
        self.plot_widget.showGrid(x=True, y=True)
        right_panel_layout.addWidget(self.plot_widget, 2)

        # Metrics and CLI section
        bottom_right_layout = QHBoxLayout()
        right_panel_layout.addLayout(bottom_right_layout, 1)

        metrics_group = QGroupBox("4. Performance Metrics")
        metrics_layout = QFormLayout(metrics_group)

        self.metrics_overshoot_current = QLabel("N/A")
        self.metrics_overshoot_proposed = QLabel("N/A")
        self.metrics_rise_time_current = QLabel("N/A")
        self.metrics_rise_time_proposed = QLabel("N/A")
        self.metrics_settling_time_current = QLabel("N/A")
        self.metrics_settling_time_proposed = QLabel("N/A")
        self.metrics_oscillation_current = QLabel("N/A")
        self.metrics_oscillation_proposed = QLabel("N/A")

        metrics_layout.addRow(QLabel("<b>Metric</b>"), QHBoxLayout()) # Title row hack
        metrics_layout.itemAt(0, QFormLayout.ItemRole.LabelRole).widget().setStyleSheet("font-weight: bold;")

        # A bit of a layout trick to make two columns
        current_label = QLabel("<b>Current</b>")
        proposed_label = QLabel("<b>Proposed</b>")
        metrics_title_layout = QHBoxLayout()
        metrics_title_layout.addWidget(current_label)
        metrics_title_layout.addWidget(proposed_label)
        metrics_layout.addRow("", metrics_title_layout)

        metrics_layout.addRow("Overshoot (%):", self._create_metric_row(self.metrics_overshoot_current, self.metrics_overshoot_proposed))
        metrics_layout.addRow("Rise Time (s):", self._create_metric_row(self.metrics_rise_time_current, self.metrics_rise_time_proposed))
        metrics_layout.addRow("Settling Time (s):", self._create_metric_row(self.metrics_settling_time_current, self.metrics_settling_time_proposed))
        metrics_layout.addRow("Oscillation:", self._create_metric_row(self.metrics_oscillation_current, self.metrics_oscillation_proposed))

        bottom_right_layout.addWidget(metrics_group)

        cli_group = QGroupBox("5. Betaflight CLI Commands")
        cli_layout = QVBoxLayout(cli_group)
        self.cli_output_text = QTextEdit()
        self.cli_output_text.setReadOnly(True)
        self.cli_output_text.setFontFamily("monospace")
        self.cli_output_text.setPlaceholderText("CLI commands will be generated here...")
        cli_layout.addWidget(self.cli_output_text)
        bottom_right_layout.addWidget(cli_group)

        # --- Connections ---
        self.load_dump_button.clicked.connect(self.on_load_dump)
        self.propose_button.clicked.connect(self.on_generate_proposal)
        self.update_simulation_button.clicked.connect(self.run_simulations_and_update_cli)

        # Simulation settings connections
        self.noise_checkbox.toggled.connect(self.noise_level_spinbox.setEnabled)
        self.noise_checkbox.toggled.connect(lambda: self.run_simulations_and_update_cli())
        self.noise_level_spinbox.valueChanged.connect(lambda: self.run_simulations_and_update_cli())
        self.wind_gust_button.clicked.connect(self.on_simulate_wind_gust)

    def on_load_dump(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Betaflight Dump", "", "Text Files (*.txt);;All Files (*)")
        if not filepath:
            return

        # --- Backup Logic ---
        backup_path = filepath + ".bak"
        if not os.path.exists(backup_path):
            try:
                shutil.copy2(filepath, backup_path)
                print(f"Created backup at: {backup_path}")
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
        self.update_ui_with_pids(self.current_pids)
        self.run_simulations_and_update_cli(is_initial_run=True)

    def update_ui_with_pids(self, pids):
        self.current_p_roll.setText(str(pids.get('p_roll', 'N/A')))
        self.current_i_roll.setText(str(pids.get('i_roll', 'N/A')))
        self.current_d_roll.setText(str(pids.get('d_roll', 'N/A')))
        self.current_p_pitch.setText(str(pids.get('p_pitch', 'N/A')))
        self.current_i_pitch.setText(str(pids.get('i_pitch', 'N/A')))
        self.current_d_pitch.setText(str(pids.get('d_pitch', 'N/A')))

        self.proposed_d_roll.setValue(pids.get('d_roll', 0))
        self.proposed_d_pitch.setValue(pids.get('d_pitch', 0))

    def on_generate_proposal(self):
        if not self.current_pids:
            return

        # Show a busy cursor while the optimization is running
        self.setCursor(pg.QtCore.Qt.CursorShape.WaitCursor)

        # Run the optimization algorithm
        self.proposed_pids = find_optimal_tune(self.current_pids)

        # Restore the cursor
        self.setCursor(pg.QtCore.Qt.CursorShape.ArrowCursor)

        # Update the UI with the newly found values
        # Note: The optimizer might have changed P-gains as well, so we update everything
        self.proposed_d_roll.setValue(self.proposed_pids.get('d_roll', 0))
        self.proposed_d_pitch.setValue(self.proposed_pids.get('d_pitch', 0))

        # We also need labels for proposed P-gains, but for now this is sufficient
        # to prove the concept. The UI can be expanded later.

        self.run_simulations_and_update_cli()
        self.update_simulation_button.setEnabled(True)

    def on_simulate_wind_gust(self):
        # We will apply a disturbance at t=0.1s with a magnitude of 20
        self.run_simulations_and_update_cli(disturbance_magnitude=20.0, disturbance_time=0.1)

    def run_simulations_and_update_cli(self, is_initial_run=False, disturbance_magnitude=0.0, disturbance_time=0.0):
        if not self.current_pids:
            return

        self.plot_widget.clear()

        noise_level = self.noise_level_spinbox.value() if self.noise_checkbox.isChecked() else 0.0

        # Simulate "before"
        time, response_before, d_trace_before = simulate_step_response(
            self.current_pids, noise_level=noise_level,
            disturbance_magnitude=disturbance_magnitude, disturbance_time=disturbance_time
        )
        if time is not None:
            self.plot_widget.plot(time, response_before, pen='r', name='Current Tune')
            metrics_before = calculate_response_metrics(time, response_before)
            self._update_metrics_display(metrics_before, is_current=True)

        if is_initial_run:
            return

        # Get proposed values from UI
        self.proposed_pids = self.current_pids.copy()
        self.proposed_pids['d_roll'] = self.proposed_d_roll.value()
        self.proposed_pids['d_pitch'] = self.proposed_d_pitch.value()

        # Simulate "after"
        time, response_after, d_trace_after = simulate_step_response(
            self.proposed_pids, noise_level=noise_level,
            disturbance_magnitude=disturbance_magnitude, disturbance_time=disturbance_time
        )
        if time is not None:
            self.plot_widget.plot(time, response_after, pen='g', name='Proposed Tune')
            metrics_after = calculate_response_metrics(time, response_after)
            self._update_metrics_display(metrics_after, is_current=False)

        # Update CLI
        self.cli_output_text.setText(generate_cli(self.proposed_pids))

        warnings = validate_settings(self.proposed_pids)
        if warnings:
            warning_text = "The following proposed values are outside of the recommended safe ranges:\n\n" + "\n".join(warnings)
            QMessageBox.warning(self, "Safety Warning", warning_text)

    def _create_metric_row(self, label1, label2):
        layout = QHBoxLayout()
        layout.addWidget(label1)
        layout.addWidget(label2)
        return layout

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
        # This tab is self-contained and does not depend on blackbox logs
        pass
