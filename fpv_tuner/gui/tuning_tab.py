import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTextEdit, QSpinBox, QPushButton,
    QFileDialog, QGroupBox, QLabel, QMessageBox
)
from PyQt6.QtCore import pyqtSignal
import pyqtgraph as pg

# Import backend logic
from fpv_tuner.analysis.tuning import parse_dump, propose_tune, generate_cli, simulate_step_response

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

        left_panel_layout.addStretch()

        # --- Right Panel Widgets ---
        self.plot_widget = pg.PlotWidget(title="Simulated Step Response")
        self.plot_widget.addLegend()
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.setLabel('left', 'Response')
        self.plot_widget.showGrid(x=True, y=True)
        right_panel_layout.addWidget(self.plot_widget, 2)

        cli_group = QGroupBox("4. Betaflight CLI Commands")
        cli_layout = QVBoxLayout(cli_group)
        self.cli_output_text = QTextEdit()
        self.cli_output_text.setReadOnly(True)
        self.cli_output_text.setFontFamily("monospace")
        self.cli_output_text.setPlaceholderText("CLI commands will be generated here...")
        cli_layout.addWidget(self.cli_output_text)
        right_panel_layout.addWidget(cli_group, 1)

        # --- Connections ---
        self.load_dump_button.clicked.connect(self.on_load_dump)
        self.propose_button.clicked.connect(self.on_generate_proposal)
        self.update_simulation_button.clicked.connect(self.run_simulations_and_update_cli)

    def on_load_dump(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Betaflight Dump", "", "Text Files (*.txt);;All Files (*)")
        if not filepath:
            return

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

        # Set proposed values in spinboxes
        self.proposed_d_roll.setValue(pids.get('d_roll', 0))
        self.proposed_d_pitch.setValue(pids.get('d_pitch', 0))

    def on_generate_proposal(self):
        if not self.current_pids:
            return

        self.proposed_pids = propose_tune(self.current_pids)
        self.proposed_d_roll.setValue(self.proposed_pids.get('d_roll', 0))
        self.proposed_d_pitch.setValue(self.proposed_pids.get('d_pitch', 0))

        self.run_simulations_and_update_cli()
        self.update_simulation_button.setEnabled(True)

    def run_simulations_and_update_cli(self, is_initial_run=False):
        if not self.current_pids:
            return

        self.plot_widget.clear()

        # Simulate "before"
        time, response_before = simulate_step_response(self.current_pids)
        if time is not None:
            self.plot_widget.plot(time, response_before, pen='r', name='Current Tune')

        if is_initial_run:
            return # Don't plot proposed if we just loaded

        # Get proposed values from UI
        self.proposed_pids = self.current_pids.copy()
        self.proposed_pids['d_roll'] = self.proposed_d_roll.value()
        self.proposed_pids['d_pitch'] = self.proposed_d_pitch.value()

        # Simulate "after"
        time, response_after = simulate_step_response(self.proposed_pids)
        if time is not None:
            self.plot_widget.plot(time, response_after, pen='g', name='Proposed Tune')

        # Update CLI
        self.cli_output_text.setText(generate_cli(self.proposed_pids))

    def set_data(self, logs):
        # This tab is self-contained and does not depend on blackbox logs
        pass
