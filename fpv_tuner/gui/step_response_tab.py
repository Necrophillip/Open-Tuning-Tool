import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QFormLayout, QTextEdit, QSpinBox, QPushButton,
    QSlider, QLabel
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg
import numpy as np
from fpv_tuner.analysis.system_identification import analyze_step_response, guess_optimal_params
from fpv_tuner.analysis.utils import apply_smoothing

class StepResponseTab(QWidget):
    AXES_MAP = {
        "Roll":  {'rc': 'rcCommand[0]', 'gyro': 'gyroADC[0]', 'dterm': 'axisD[0]'},
        "Pitch": {'rc': 'rcCommand[1]', 'gyro': 'gyroADC[1]', 'dterm': 'axisD[1]'},
        "Yaw":   {'rc': 'rcCommand[2]', 'gyro': 'gyroADC[2]', 'dterm': 'axisD[2]'},
    }
    # Using a more distinct color for D-Term
    PLOT_COLORS = {"rc": "b", "gyro": "r", "dterm": "g"}

    def __init__(self):
        super().__init__()
        self.logs = {}

        main_layout = QVBoxLayout(self)

        # --- Top Controls ---
        controls_container = QWidget()
        controls_layout = QHBoxLayout(controls_container)
        main_layout.addWidget(controls_container)

        # --- Content Layout (Plot + Metrics) ---
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        self.plot_widget = pg.PlotWidget(title="Step Response Analysis")
        self.plot_widget.addLegend()
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.setLabel('left', 'Value')
        self.plot_widget.showGrid(x=True, y=True)
        content_layout.addWidget(self.plot_widget, 3)

        self.metrics_text = QTextEdit()
        self.metrics_text.setReadOnly(True)
        self.metrics_text.setFontFamily("monospace")
        content_layout.addWidget(self.metrics_text, 1)

        # --- Populate Top Controls ---
        form_layout = QFormLayout()
        self.log_combo = QComboBox()
        self.axis_combo = QComboBox()
        self.axis_combo.addItems(list(self.AXES_MAP.keys()))

        self.threshold_spinbox = QSpinBox()
        self.threshold_spinbox.setRange(1, 1000)
        self.threshold_spinbox.setValue(30)
        self.threshold_spinbox.setSingleStep(5)
        self.threshold_spinbox.setSuffix(" (RC Change)")

        self.std_dev_spinbox = QSpinBox()
        self.std_dev_spinbox.setRange(1, 1000)
        self.std_dev_spinbox.setValue(50)
        self.std_dev_spinbox.setSingleStep(5)
        self.std_dev_spinbox.setSuffix(" (Noise Tol.)")

        form_layout.addRow("Log File:", self.log_combo)
        form_layout.addRow("Axis:", self.axis_combo)
        form_layout.addRow("Detection Threshold:", self.threshold_spinbox)
        form_layout.addRow("Noise Tolerance:", self.std_dev_spinbox)

        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setRange(50, 2000)
        self.duration_spinbox.setValue(100)
        self.duration_spinbox.setSingleStep(50)
        self.duration_spinbox.setSuffix(" ms")
        form_layout.addRow("Post-Step Duration:", self.duration_spinbox)

        smoothing_layout = QHBoxLayout()
        smoothing_layout.addWidget(QLabel("Smoothing Level:"))
        self.smoothing_slider = QSlider(Qt.Orientation.Horizontal)
        self.smoothing_slider.setRange(0, 20)
        self.smoothing_slider.setValue(0)
        self.smoothing_slider.setTickInterval(5)
        self.smoothing_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.smoothing_label = QLabel("Raw")
        smoothing_layout.addWidget(self.smoothing_slider)
        smoothing_layout.addWidget(self.smoothing_label)
        form_layout.addRow(smoothing_layout)

        self.auto_tune_button = QPushButton("Auto-Tune Params")

        # Add a separate layout for the button to control its alignment
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.auto_tune_button)

        controls_layout.addLayout(form_layout)
        controls_layout.addLayout(button_layout)
        controls_layout.addStretch()

        # --- Connections ---
        self.log_combo.currentTextChanged.connect(self.run_analysis)
        self.axis_combo.currentTextChanged.connect(self.run_analysis)
        self.threshold_spinbox.valueChanged.connect(self.run_analysis)
        self.std_dev_spinbox.valueChanged.connect(self.run_analysis)
        self.duration_spinbox.valueChanged.connect(self.run_analysis)
        self.auto_tune_button.clicked.connect(self.on_auto_tune_clicked)
        self.smoothing_slider.valueChanged.connect(self.on_smoothing_changed)

    def on_smoothing_changed(self, value):
        if value == 0:
            self.smoothing_label.setText("Raw")
        else:
            self.smoothing_label.setText(f"Level {value}")
        self.run_analysis()

    def on_auto_tune_clicked(self):
        log_name = self.log_combo.currentText()
        axis_name = self.axis_combo.currentText()

        if not log_name or not axis_name or not self.logs:
            return

        for path, df in self.logs.items():
            if os.path.basename(path) == log_name:
                log_data = df
                break
        else:
            return

        cols = self.AXES_MAP[axis_name]
        rc_col = self._find_column(log_data, [cols['rc']])
        if not rc_col:
            return

        rc_data = log_data[rc_col].to_numpy()

        params = guess_optimal_params(rc_data)

        self.threshold_spinbox.setValue(params['threshold'])
        self.std_dev_spinbox.setValue(params['std_dev_max'])
        # Setting the value will automatically trigger run_analysis due to the connection

    def set_data(self, logs):
        self.logs = logs
        self.log_combo.blockSignals(True)
        self.log_combo.clear()
        self.log_combo.addItems([os.path.basename(p) for p in self.logs.keys()])
        self.log_combo.blockSignals(False)

        # If there are logs, trigger analysis. Otherwise, clear everything.
        if self.logs:
            self.run_analysis()
        else:
            self.plot_widget.clear()
            self.metrics_text.clear()


    def run_analysis(self):
        self.plot_widget.clear()
        self.metrics_text.clear()

        # Get the selected log file
        log_name = self.log_combo.currentText()
        if not log_name or not self.logs:
            return

        for path, df in self.logs.items():
            if os.path.basename(path) == log_name:
                log_data = df
                break
        else:
            return

        # Get the selected axis
        axis_name = self.axis_combo.currentText()
        if not axis_name:
            return

        # --- Get Data Columns ---
        time_col = self._find_column(log_data, ['time (us)', 'time'])
        if not time_col:
            self.metrics_text.setText("Error: 'time (us)' column not found.")
            return
        time_data = log_data[time_col].to_numpy()

        cols = self.AXES_MAP[axis_name]
        rc_col = self._find_column(log_data, [cols['rc']])
        gyro_col = self._find_column(log_data, [cols['gyro']])
        dterm_col = self._find_column(log_data, [cols['dterm']])

        if not rc_col or not gyro_col:
            self.metrics_text.setText(f"Error: Missing rcCommand or gyroADC for {axis_name}.")
            return

        rc_data = log_data[rc_col].to_numpy()
        gyro_data = log_data[gyro_col].to_numpy()
        dterm_data = log_data[dterm_col].to_numpy() if dterm_col else None

        # --- Run Analysis ---
        threshold = self.threshold_spinbox.value()
        std_dev_max = self.std_dev_spinbox.value()
        duration_ms = self.duration_spinbox.value()
        results = analyze_step_response(
            time_data, rc_data, gyro_data, dterm_data, threshold=threshold, std_dev_max=std_dev_max, post_step_duration_ms=duration_ms
        )

        # --- Display Results ---
        self.plot_widget.setTitle(f"{axis_name} Step Response")

        if results.get("error"):
            self.metrics_text.setText(f"--- {axis_name} ---\n  {results['error']}\n\n")
            return

        # Plotting
        smoothing_level = self.smoothing_slider.value()

        time_slice_s = results["time_slice"] # Already in seconds

        rc_data_smoothed = apply_smoothing(results["rc_slice"], smoothing_level)
        gyro_data_smoothed = apply_smoothing(results["gyro_slice"], smoothing_level)

        self.plot_widget.plot(time_slice_s, rc_data_smoothed, pen=self.PLOT_COLORS['rc'], name='RC Command', autoDownsample=False)
        self.plot_widget.plot(time_slice_s, gyro_data_smoothed, pen=self.PLOT_COLORS['gyro'], name='Gyro Response', autoDownsample=False)

        if results["dterm_slice"] is not None:
            dterm_data_smoothed = apply_smoothing(results["dterm_slice"], smoothing_level)
            self.plot_widget.plot(time_slice_s, dterm_data_smoothed, pen=pg.mkPen(self.PLOT_COLORS['dterm'], style=pg.QtCore.Qt.PenStyle.DashLine), name='D-Term', autoDownsample=False)

        # Metrics are calculated on raw data, so they remain correct
        metrics = results["metrics"]
        metrics_text = f"--- {axis_name} Step Metrics ---\n"
        for key, value in metrics.items():
            if isinstance(value, (float, np.floating)):
                metrics_text += f"  {key}: {value:.4f}\n"
            else:
                metrics_text += f"  {key}: {value}\n"
        self.metrics_text.setText(metrics_text)


    def _find_column(self, df, possible_names):
        for name in possible_names:
            if name in df.columns:
                return name
        return None
