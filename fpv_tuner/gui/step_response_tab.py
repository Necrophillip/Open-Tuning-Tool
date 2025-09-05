import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel,
    QDoubleSpinBox, QFormLayout, QSpinBox, QTextEdit
)
import pyqtgraph as pg
import numpy as np
from fpv_tuner.analysis.step_response import find_step_responses, step_response_metrics

class StepResponseTab(QWidget):
    AXES_MAP = {
        "Roll": {"rc": "rcCommand[0]", "setpoint": "setpoint[0]", "gyro": "gyroADC[0]", "dterm": ['dTerm[0]', 'axisD[0]']},
        "Pitch": {"rc": "rcCommand[1]", "setpoint": "setpoint[1]", "gyro": "gyroADC[1]", "dterm": ['dTerm[1]', 'axisD[1]']},
        "Yaw": {"rc": "rcCommand[2]", "setpoint": "setpoint[2]", "gyro": "gyroADC[2]", "dterm": ['dTerm[2]', 'axisD[2]']},
    }

    def __init__(self):
        super().__init__()
        self.logs = {}
        self.current_log_path = None
        self.steps = []
        self.current_step_index = -1

        main_layout = QVBoxLayout(self)
        controls_container = QWidget()
        controls_layout = QHBoxLayout(controls_container)
        main_layout.addWidget(controls_container)

        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        self.plot_widget = pg.PlotWidget(title="Step Response")
        self.plot_widget.addLegend()
        self.plot_widget.setDownsampling(auto=True, mode='peak')
        self.plot_widget.setClipToView(True)
        content_layout.addWidget(self.plot_widget, 3)

        self.metrics_text = QTextEdit()
        self.metrics_text.setReadOnly(True)
        self.metrics_text.setFontFamily("monospace")
        content_layout.addWidget(self.metrics_text, 1)

        form_layout = QFormLayout()
        self.log_combo = QComboBox()
        self.axis_combo = QComboBox()
        self.axis_combo.addItems(self.AXES_MAP.keys())
        self.threshold_spinbox = QDoubleSpinBox()
        self.threshold_spinbox.setRange(50, 1000)
        self.threshold_spinbox.setValue(300)
        self.threshold_spinbox.setSingleStep(25)
        self.threshold_spinbox.setSuffix(" (Threshold)")

        self.pre_window_spinbox = QSpinBox()
        self.pre_window_spinbox.setRange(10, 200)
        self.pre_window_spinbox.setValue(20)
        self.pre_window_spinbox.setSuffix(" ms (Pre-Window)")

        self.post_window_spinbox = QSpinBox()
        self.post_window_spinbox.setRange(50, 1000)
        self.post_window_spinbox.setValue(200)
        self.post_window_spinbox.setSuffix(" ms (Post-Window)")

        form_layout.addRow("Log File:", self.log_combo)
        form_layout.addRow("Axis:", self.axis_combo)
        form_layout.addRow("Sensitivity:", self.threshold_spinbox)
        form_layout.addRow("Window:", self.pre_window_spinbox)
        form_layout.addRow("", self.post_window_spinbox)
        controls_layout.addLayout(form_layout)

        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("<< Previous")
        self.step_label = QLabel("No steps found")
        self.next_button = QPushButton("Next >>")
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.step_label)
        nav_layout.addWidget(self.next_button)
        controls_layout.addLayout(nav_layout)
        controls_layout.addStretch()

        self.log_combo.currentTextChanged.connect(self.on_log_selection_change)
        self.axis_combo.currentTextChanged.connect(self.analyze_axis)
        self.threshold_spinbox.valueChanged.connect(self.analyze_axis)
        self.pre_window_spinbox.valueChanged.connect(self.analyze_axis)
        self.post_window_spinbox.valueChanged.connect(self.analyze_axis)
        self.prev_button.clicked.connect(self.prev_step)
        self.next_button.clicked.connect(self.next_step)

    def set_data(self, logs):
        self.logs = logs
        self.log_combo.blockSignals(True)
        self.log_combo.clear()
        self.log_combo.addItems([os.path.basename(p) for p in self.logs.keys()])
        self.log_combo.blockSignals(False)

        if self.logs:
            self.on_log_selection_change(self.log_combo.currentText())
        else:
            self.current_log_path = None
            self.analyze_axis()

    def on_log_selection_change(self, text):
        for path in self.logs.keys():
            if os.path.basename(path) == text:
                self.current_log_path = path
                break
        self.analyze_axis()

    def analyze_axis(self):
        self.current_step_index = -1
        self.steps = []
        if not self.current_log_path or self.current_log_path not in self.logs:
            self.update_plot()
            return

        log_data = self.logs[self.current_log_path]
        axis = self.axis_combo.currentText()
        rc_col = self._find_column(log_data, [self.AXES_MAP[axis]["rc"]])
        time_col = self._find_column(log_data, ['time (us)', 'time'])

        threshold = self.threshold_spinbox.value()
        pre_ms = self.pre_window_spinbox.value()
        post_ms = self.post_window_spinbox.value()

        if rc_col and time_col:
            self.steps = find_step_responses(
                log_data[rc_col],
                log_data[time_col],
                threshold=threshold,
                pre_step_flat_ms=pre_ms,
                post_step_flat_ms=post_ms
            )

        if self.steps:
            self.current_step_index = 0
        self.update_plot()

    def prev_step(self):
        if self.steps and self.current_step_index > 0:
            self.current_step_index -= 1
            self.update_plot()

    def next_step(self):
        if self.steps and self.current_step_index < len(self.steps) - 1:
            self.current_step_index += 1
            self.update_plot()

    def update_plot(self):
        self.plot_widget.clear()
        self.metrics_text.clear()

        if self.current_step_index == -1:
            self.step_label.setText("No steps found")
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return

        log_data = self.logs[self.current_log_path]
        self.step_label.setText(f"Step {self.current_step_index + 1} of {len(self.steps)}")
        self.prev_button.setEnabled(self.current_step_index > 0)
        self.next_button.setEnabled(self.current_step_index < len(self.steps) - 1)

        start, step_idx, end = self.steps[self.current_step_index]
        axis = self.axis_combo.currentText()
        cols = self.AXES_MAP[axis]
        time_us_col = self._find_column(log_data, ['time (us)', 'time'])
        if time_us_col is None: return

        time_s = log_data[time_us_col] / 1_000_000

        time_slice = time_s.iloc[start:end].copy().reset_index(drop=True)
        rc_slice = log_data[self._find_column(log_data, [cols["rc"]])].iloc[start:end].copy().reset_index(drop=True)
        gyro_slice = log_data[self._find_column(log_data, [cols["gyro"]])].iloc[start:end].copy().reset_index(drop=True)
        dterm_col = self._find_column(log_data, cols["dterm"])

        self.plot_widget.addItem(pg.InfiniteLine(pos=time_s.iloc[step_idx], angle=90, movable=False, pen='gray'))
        self.plot_widget.plot(time_slice, rc_slice, pen='c', name='RC Command')
        self.plot_widget.plot(time_slice, gyro_slice, pen='y', name='Gyro')
        if dterm_col:
            dterm_slice = log_data[dterm_col].iloc[start:end].copy().reset_index(drop=True)
            self.plot_widget.plot(time_slice, dterm_slice, pen='m', name='D-Term')

        metrics = step_response_metrics(time_slice, rc_slice, gyro_slice)
        metrics_str = "--- Step Response Metrics ---\n\n"
        for key, value in metrics.items():
            if isinstance(value, float):
                metrics_str += f"{key:<20}: {value:.4f}\n"
            else:
                metrics_str += f"{key:<20}: {value}\n"
        self.metrics_text.setText(metrics_str)

    def _find_column(self, df, possible_names):
        for name in possible_names:
            if name in df.columns:
                return name
        return None
