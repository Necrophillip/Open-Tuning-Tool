import os
import shutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTextEdit, QSpinBox, QPushButton,
    QFileDialog, QGroupBox, QLabel, QMessageBox, QCheckBox, QDoubleSpinBox, QGridLayout,
    QComboBox, QSlider, QScrollArea
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg

from fpv_tuner.analysis.tuning import (
    DRONE_PROFILES, calculate_response_metrics, classify_step_response,
    extract_step_response_from_log, propose_pids_from_metrics, generate_cli,
    parse_dump, simulate_step_response, propose_pids_from_simulation,
    propose_pids_from_bbl_and_cli
)
from fpv_tuner.analysis.blackbox_parser import get_blackbox_headers
from fpv_tuner.blackbox.loader import load_log
from fpv_tuner.analysis.utils import apply_smoothing

class TuningTab(QWidget):
    dump_filepath = None
    current_pids = {}
    bb_log_path = None
    loaded_logs = {}

    def __init__(self):
        super().__init__()
        main_layout = QHBoxLayout(self)

        # --- Left Panel with Scroll Area ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        left_panel_container = QWidget()
        left_panel_layout = QVBoxLayout(left_panel_container)

        self._create_load_controls(left_panel_layout)
        self._create_scope_controls(left_panel_layout)
        self._create_plot_settings_controls(left_panel_layout)
        self._create_proposal_display(left_panel_layout)
        self._create_model_params_display(left_panel_layout)
        left_panel_layout.addStretch()

        scroll_area.setWidget(left_panel_container)

        # --- Right Panel ---
        right_panel_layout = QVBoxLayout()
        self._create_plot_controls(right_panel_layout)
        self._create_bottom_right_controls(right_panel_layout)

        # --- Main Layout Assembly ---
        main_layout.addWidget(scroll_area, 2) # Add scroll area with stretch factor
        main_layout.addLayout(right_panel_layout, 5)

        self._connect_signals()

    def _create_load_controls(self, parent_layout):
        group = QGroupBox("1. Load Files")
        layout = QVBoxLayout(group)

        # CLI loading
        cli_layout = QHBoxLayout()
        self.load_dump_button = QPushButton("Load CLI File")
        self.load_dump_button.setFixedWidth(150)
        self.dump_file_label = QLabel("No file loaded.")
        cli_layout.addWidget(self.load_dump_button)
        cli_layout.addWidget(self.dump_file_label)
        layout.addLayout(cli_layout)

        # BBL loading
        bbl_load_widget = QWidget()
        bbl_load_layout = QHBoxLayout(bbl_load_widget)
        bbl_load_layout.setContentsMargins(0, 0, 0, 0)
        self.load_bb_button = QPushButton("Load .BBL File")
        self.load_bb_button.setFixedWidth(150)
        self.bb_file_label = QLabel("No file loaded.")
        bbl_load_layout.addWidget(self.load_bb_button)
        bbl_load_layout.addWidget(self.bb_file_label)
        self.bb_log_combo = QComboBox()
        bbl_load_layout.addWidget(self.bb_log_combo)
        self.bb_log_combo.setVisible(False)
        layout.addWidget(bbl_load_widget)

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

    def _create_plot_settings_controls(self, parent_layout):
        group = QGroupBox("3. Plot Settings")
        layout = QFormLayout(group)

        self.smoothing_slider = QSlider(Qt.Orientation.Horizontal)
        self.smoothing_slider.setRange(0, 20)
        self.smoothing_slider.setValue(5) # Default smoothing
        self.smoothing_label = QLabel("Level 5")
        smoothing_layout = QHBoxLayout()
        smoothing_layout.addWidget(self.smoothing_slider)
        smoothing_layout.addWidget(self.smoothing_label)
        layout.addRow("Plot Smoothing:", smoothing_layout)

        parent_layout.addWidget(group)

    def _create_plot_controls(self, parent_layout):
        self.plot_widget = pg.PlotWidget(title="Simulated Step Response")
        self.plot_widget.addLegend()
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.setLabel('left', 'Response / PID Output')
        self.plot_widget.showGrid(x=True, y=True)
        parent_layout.addWidget(self.plot_widget, 2)

    def _create_bottom_right_controls(self, parent_layout):
        metrics_group = QGroupBox("Performance Metrics")
        metrics_layout = QFormLayout(metrics_group)

        self.metrics_overshoot = QLabel("N/A")
        self.metrics_rise_time = QLabel("N/A")
        self.metrics_settling_time = QLabel("N/A")
        self.metrics_oscillation = QLabel("N/A")
        self.classification = QLabel("N/A")

        metrics_layout.addRow("Overshoot (%):", self.metrics_overshoot)
        metrics_layout.addRow("Rise Time (s):", self.metrics_rise_time)
        metrics_layout.addRow("Settling Time (s):", self.metrics_settling_time)
        metrics_layout.addRow("Oscillation:", self.metrics_oscillation)
        metrics_layout.addRow("Classification:", self.classification)

        parent_layout.addWidget(metrics_group, 1)

    def _create_proposal_display(self, parent_layout):
        group = QGroupBox("4. Proposed Tune")
        layout = QVBoxLayout(group)

        # PID Table
        pid_layout = QGridLayout()
        headers = ["Axis", "P", "I", "D"]
        for i, header in enumerate(headers):
            pid_layout.addWidget(QLabel(f"<b>{header}</b>"), 0, i)

        self.pid_labels = {}
        for i, axis in enumerate(["Roll", "Pitch", "Yaw"]):
            row = i + 1
            pid_layout.addWidget(QLabel(axis), row, 0)
            for j, term in enumerate(["p", "i", "d"]):
                key = f"{term}_{axis.lower()}"
                self.pid_labels[key] = QLabel("N/A")
                pid_layout.addWidget(self.pid_labels[key], row, j + 1)

        layout.addLayout(pid_layout)

        # CLI Output
        cli_group = QGroupBox("CLI Commands")
        cli_layout = QVBoxLayout(cli_group)
        self.cli_output_text = QTextEdit()
        self.cli_output_text.setReadOnly(True)
        self.cli_output_text.setFontFamily("monospace")
        self.cli_output_text.setMaximumHeight(150)
        cli_layout.addWidget(self.cli_output_text)
        layout.addWidget(cli_group)

        parent_layout.addWidget(group)

    def _create_model_params_display(self, parent_layout):
        group = QGroupBox("5. Model Parameters")
        layout = QFormLayout(group)

        self.model_param_labels = {
            "k1": QLabel("N/A"), "tau": QLabel("N/A"),
            "k2": QLabel("N/A"), "wn": QLabel("N/A"), "zeta": QLabel("N/A"),
        }

        layout.addRow("<b>1st Order (K, τ):</b>", self._create_param_row(self.model_param_labels["k1"], self.model_param_labels["tau"]))
        layout.addRow("<b>2nd Order (K, ωn, ζ):</b>", self._create_param_row(self.model_param_labels["k2"], self.model_param_labels["wn"], self.model_param_labels["zeta"]))

        parent_layout.addWidget(group)

    def _create_param_row(self, *labels):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        for label in labels:
            layout.addWidget(label)
        layout.setContentsMargins(0,0,0,0)
        return widget

    def _update_model_params_display(self, analysis_results):
        popt1 = analysis_results.get("popt1", [np.nan, np.nan])
        popt2 = analysis_results.get("popt2", [np.nan, np.nan, np.nan])

        self.model_param_labels["k1"].setText(f"{popt1[0]:.3f}")
        self.model_param_labels["tau"].setText(f"{popt1[1]:.4f}")
        self.model_param_labels["k2"].setText(f"{popt2[0]:.3f}")
        self.model_param_labels["wn"].setText(f"{popt2[1]:.2f}")
        self.model_param_labels["zeta"].setText(f"{popt2[2]:.3f}")

    def _connect_signals(self):
        self.load_dump_button.clicked.connect(self.on_load_dump)
        self.load_bb_button.clicked.connect(self.on_load_blackbox)
        self.bb_log_combo.currentIndexChanged.connect(self.on_bbl_log_selected)
        self.axis_combo.currentTextChanged.connect(self.update_display_and_propose)
        self.profile_combo.currentTextChanged.connect(self.update_display_and_propose)
        self.smoothing_slider.valueChanged.connect(self.on_smoothing_label_changed)
        self.smoothing_slider.valueChanged.connect(self.update_display_and_propose)

    def on_smoothing_label_changed(self, value):
        if value == 0:
            self.smoothing_label.setText("Raw")
        else:
            self.smoothing_label.setText(f"Level {value}")

    def on_load_dump(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Betaflight Dump", "", "Text Files (*.txt);;All Files (*)")
        if not filepath: return

        pids, _, error = parse_dump(filepath) # We don't need version anymore
        if error:
            QMessageBox.critical(self, "Error Parsing Dump", error)
            return

        self.dump_filepath = filepath
        self.current_pids = pids
        self.dump_file_label.setText(os.path.basename(filepath))

        # If a BBL is loaded, a CLI load will just supplement it.
        # If not, it becomes the primary source.
        self.update_display_and_propose()

    def on_bbl_log_selected(self, index):
        filepath = self.bb_log_combo.itemData(index)
        if not filepath:
            self.bb_log_path = None
            self.plot_widget.clear()
            self._update_metrics_display({})
            self._update_classification_display({})
            self._update_proposal_display({})
            return

        self.bb_log_path = filepath
        self.bb_file_label.setText(os.path.basename(filepath))
        self.update_display_and_propose()

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
        self.update_display_and_propose()

    def update_display_and_propose(self):
        self.plot_widget.clear()
        axis_to_analyze = self.axis_combo.currentText().lower()
        profile_name = self.profile_combo.currentText()
        drone_profile = DRONE_PROFILES.get(profile_name, DRONE_PROFILES["Default"])

        has_bbl = self.bb_log_path and self.bb_log_path in self.loaded_logs
        has_cli = self.dump_filepath and self.current_pids

        # Scenario 1: Blackbox data is available (priority)
        if has_bbl:
            log_data = self.loaded_logs[self.bb_log_path]
            analysis_results = extract_step_response_from_log(log_data.copy(), axis_to_analyze)

            if analysis_results:
                t, y, y1, p1, y2, p2 = (analysis_results.get(k) for k in ["t_avg", "y_avg", "y_fit1", "popt1", "y_fit2", "popt2"])

                self.plot_widget.plot(t, y, pen={'color': 'k', 'width': 2}, name='Avg. Real Response')
                if not np.isnan(p1[0]):
                    self.plot_widget.plot(t, y1, pen={'color': 'b', 'style': Qt.PenStyle.DashLine}, name='1st Order Fit')
                if not np.isnan(p2[0]):
                    self.plot_widget.plot(t, y2, pen={'color': 'r', 'style': Qt.PenStyle.DashLine}, name='2nd Order Fit')

                metrics = calculate_response_metrics(t, y)
                self._update_metrics_display(metrics)
                self._update_classification_display(metrics)
                self._update_model_params_display(analysis_results)

                # Propose PIDs based on BBL analysis, using CLI as base if available
                if has_cli:
                    proposed_pids = propose_pids_from_bbl_and_cli(self.current_pids, log_data.copy(), drone_profile, axis_to_analyze)
                else:
                    proposed_pids = propose_pids_from_metrics(metrics, drone_profile)
                self._update_proposal_display(proposed_pids)

            else:
                self._show_plot_message("Could not extract step response from Blackbox log.")
                self._update_model_params_display({}) # Clear params

        # Scenario 3: Only CLI data is available
        elif has_cli:
            inertia = drone_profile.get("inertia", 0.005)
            sim_time, sim_response = simulate_step_response(self.current_pids, axis_to_analyze, inertia)
            if sim_time is not None:
                self.plot_widget.plot(sim_time, sim_response, pen='c', name='Simulated Step Response')
                metrics = calculate_response_metrics(sim_time, sim_response)
                proposed_pids = propose_pids_from_simulation(self.current_pids, drone_profile)
                self._update_metrics_display(metrics)
                self._update_classification_display(metrics)
                self._update_proposal_display(proposed_pids)
            else:
                self._show_plot_message("Could not simulate step response from CLI PIDs.")

        # Scenario 4: No data loaded
        else:
            self._show_plot_message("Load a Blackbox log or CLI dump to begin.")

    def _show_plot_message(self, message, corner='center'):
        self._update_metrics_display({})
        self._update_classification_display({})
        self._update_proposal_display({})

        if corner == 'topLeft':
            anchor = (0, 0)
            pos = (self.plot_widget.getViewBox().viewRange()[0][0], self.plot_widget.getViewBox().viewRange()[1][1])
        else: # center
            anchor = (0.5, 0.5)
            pos = None # pyqtgraph will center it

        text_item = pg.TextItem(message, anchor=anchor)
        self.plot_widget.addItem(text_item)
        if pos:
            text_item.setPos(pos[0], pos[1])


    def _update_metrics_display(self, metrics):
        self.metrics_overshoot.setText(f"{metrics.get('Overshoot (%)', 0):.2f}")
        self.metrics_rise_time.setText(f"{metrics.get('Rise Time (s)', 0):.4f}")
        self.metrics_settling_time.setText(f"{metrics.get('Settling Time (s)', 0):.4f}")
        self.metrics_oscillation.setText(f"{metrics.get('Oscillation', 0):.2f}")

    def _update_classification_display(self, metrics):
        text, color = classify_step_response(metrics)
        label = self.classification
        label.setText(text)
        label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _update_proposal_display(self, pids):
        if not pids:
            for label in self.pid_labels.values():
                label.setText("N/A")
            self.cli_output_text.clear()
            return

        for key, label in self.pid_labels.items():
            label.setText(str(pids.get(key, "N/A")))

        self.cli_output_text.setText(generate_cli(pids))

    def set_data(self, logs):
        self.loaded_logs = logs
        self.bb_log_combo.clear()

        if logs:
            self.bb_log_combo.addItem("Select a loaded BBL...", userData=None)
            for path, data in logs.items():
                self.bb_log_combo.addItem(os.path.basename(path), userData=path)

            self.load_bb_button.setVisible(False)
            self.bb_file_label.setVisible(False)
            self.bb_log_combo.setVisible(True)
        else:
            self.load_bb_button.setVisible(True)
            self.bb_file_label.setVisible(True)
            self.bb_log_combo.setVisible(False)
