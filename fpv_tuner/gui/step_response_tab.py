import os
import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QFormLayout, QTextEdit,
    QPushButton, QLabel, QFileDialog, QDoubleSpinBox, QSpinBox
)
from scipy.signal import savgol_filter
import pyqtgraph as pg

class StepResponseTab(QWidget):
    AXES_MAP = {
        "Roll": {
            'rc': ['rcCommand[0]', 'axisCmd[0]'],
            'gyro': ['gyroADC[0]', 'gyro[0]', 'gyro_roll']
        },
        "Pitch": {
            'rc': ['rcCommand[1]', 'axisCmd[1]'],
            'gyro': ['gyroADC[1]', 'gyro[1]', 'gyro_pitch']
        },
        "Yaw": {
            'rc': ['rcCommand[2]', 'axisCmd[2]'],
            'gyro': ['gyroADC[2]', 'gyro[2]', 'gyro_yaw']
        },
    }
    PLOT_COLORS = {"rc": "#FFA726", "gyro": "#42A5F5"}

    def __init__(self):
        super().__init__()
        self.logs = {}
        self.loop_freq = 8000

        main_layout = QVBoxLayout(self)
        controls_container = QWidget()
        controls_layout = QHBoxLayout(controls_container)
        main_layout.addWidget(controls_container)

        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        self.plot_widget = pg.PlotWidget(title="Step Response Analysis")
        self.plot_widget.addLegend()
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.setLabel('left', 'Normalized Response')
        self.plot_widget.showGrid(x=True, y=True)
        content_layout.addWidget(self.plot_widget, 3)

        self.metrics_text = QTextEdit()
        self.metrics_text.setReadOnly(True)
        self.metrics_text.setFontFamily("monospace")
        content_layout.addWidget(self.metrics_text, 1)

        form_layout = QFormLayout()
        self.log_combo = QComboBox()
        self.axis_combo = QComboBox()
        self.axis_combo.addItems(list(self.AXES_MAP.keys()))

        form_layout.addRow("Log File:", self.log_combo)
        form_layout.addRow("Axis:", self.axis_combo)

        self.threshold_spinbox = QDoubleSpinBox()
        self.threshold_spinbox.setRange(0.01, 1.0)
        self.threshold_spinbox.setValue(0.5)
        self.threshold_spinbox.setSingleStep(0.05)
        self.threshold_spinbox.setSuffix(" (RC Change)")
        form_layout.addRow("Detection Threshold:", self.threshold_spinbox)

        self.loop_freq_spinbox = QSpinBox()
        self.loop_freq_spinbox.setRange(100, 16000)
        self.loop_freq_spinbox.setValue(self.loop_freq)
        self.loop_freq_spinbox.setSingleStep(100)
        self.loop_freq_spinbox.setSuffix(" Hz")
        form_layout.addRow("Loop Frequency:", self.loop_freq_spinbox)

        controls_layout.addLayout(form_layout)
        controls_layout.addStretch()

        self.log_combo.currentTextChanged.connect(self.run_analysis)
        self.axis_combo.currentTextChanged.connect(self.run_analysis)
        self.threshold_spinbox.valueChanged.connect(self.run_analysis)
        self.loop_freq_spinbox.valueChanged.connect(self.run_analysis)

    def set_data(self, logs):
        self.logs = logs
        self.log_combo.blockSignals(True)
        self.log_combo.clear()
        self.log_combo.addItems([os.path.basename(p) for p in self.logs.keys()])
        self.log_combo.blockSignals(False)
        self.run_analysis()

    def run_analysis(self):
        self.plot_widget.clear()
        self.metrics_text.clear()

        log_name = self.log_combo.currentText()
        if not log_name or not self.logs:
            return

        log_data_dict = next((data for path, data in self.logs.items() if os.path.basename(path) == log_name), None)
        if not log_data_dict:
            return

        log_data = log_data_dict.get('df')
        if log_data is None:
            return

        axis_name = self.axis_combo.currentText()
        if not axis_name:
            return

        time_col = self._find_column(log_data, ['time (us)', 'time', 'loopIteration'])
        if not time_col:
            self.metrics_text.setText("Error: 'time' or 'loopIteration' column not found.")
            return

        cols = self.AXES_MAP[axis_name]
        rc_col = self._find_column(log_data, cols['rc'])
        gyro_col = self._find_column(log_data, cols['gyro'])

        if rc_col is None:
            print(f"⚠️ No se encontró ninguna columna RC en {log_data.columns}")
        if gyro_col is None:
            print(f"⚠️ No se encontró ninguna columna Gyro en {log_data.columns}")

        if not rc_col or not gyro_col:
            self.metrics_text.setText(f"Error: Missing rcCommand or gyroADC for {axis_name}.")
            return

        time_data = log_data[time_col].to_numpy()
        rc_data = log_data[rc_col].to_numpy()
        gyro_data = log_data[gyro_col].to_numpy()

        threshold = self.threshold_spinbox.value()
        self.loop_freq = self.loop_freq_spinbox.value()

        step_index = self._detect_step(rc_data, threshold=threshold)
        if step_index is None:
            self.metrics_text.setText("Error: No step detected.")
            return

        time_w, rc_w, gyro_w = self._extract_window(time_data, rc_data, gyro_data, step_index, time_col)

        rc_smooth = savgol_filter(rc_w, 11, 3)
        gyro_smooth = savgol_filter(gyro_w, 11, 3)

        rc_norm, gyro_norm = self._normalize_signals(rc_smooth, gyro_smooth)

        self.plot_widget.plot(time_w, rc_norm, pen=self.PLOT_COLORS['rc'], name='RC Command')
        self.plot_widget.plot(time_w, gyro_norm, pen=self.PLOT_COLORS['gyro'], name='Gyro Response')

        metrics = self._calculate_metrics(time_w, gyro_norm)
        self.metrics_text.setText(self._format_metrics(metrics))

        self.plot_widget.setTitle(f"PID Step Response - {axis_name} Axis")

    def _calculate_metrics(self, time, response):
        metrics = {}

        # Overshoot
        overshoot = (np.max(response) - 1) * 100
        metrics['Overshoot'] = f"{overshoot:.2f} %"

        # Rise Time (10% to 90%)
        upper = np.where(response >= 0.9)[0]
        lower = np.where(response >= 0.1)[0]
        if len(upper) > 0 and len(lower) > 0:
            rise_time = time[upper[0]] - time[lower[0]]
            metrics['Rise Time'] = f"{rise_time * 1000:.2f} ms"

        # Settling Time (within 5% of final value)
        settled = np.where(np.abs(response - 1) > 0.05)[0]
        if len(settled) > 0:
            settling_time = time[settled[-1]]
            metrics['Settling Time'] = f"{settling_time * 1000:.2f} ms"

        return metrics

    def _format_metrics(self, metrics):
        return "\n".join([f"{key}: {value}" for key, value in metrics.items()])

    def _find_column(self, df, possible_names):
        if not isinstance(possible_names, list):
            possible_names = [possible_names]

        flat_names = []
        for name in possible_names:
            if isinstance(name, list):
                flat_names.extend(name)
            else:
                flat_names.append(name)

        return next((name for name in flat_names if name in df.columns), None)

    def _detect_step(self, rc_signal, threshold=0.5):
        rc_norm = (rc_signal - np.min(rc_signal)) / (np.max(rc_signal) - np.min(rc_signal))
        diffs = np.diff(rc_norm, prepend=0)
        step_indices = np.where(diffs > threshold)[0]
        return step_indices[0] if len(step_indices) > 0 else None

    def _extract_window(self, time, rc, gyro, step_index, time_col_name, pre_samples=100, post_samples=500):
        start = max(0, step_index - pre_samples)
        end = min(len(time), step_index + post_samples)

        time_window = time[start:end]
        if time_col_name == 'loopIteration':
            time_window = time_window * (1 / self.loop_freq)
        elif time_col_name == 'time (us)':
            time_window = (time_window - time_window[0]) / 1_000_000

        return time_window, rc[start:end], gyro[start:end]

    def _normalize_signals(self, rc, gyro):
        rc_norm = (rc - np.min(rc)) / (np.max(rc) - np.min(rc))
        gyro_norm = (gyro - np.min(gyro)) / (np.max(gyro) - np.min(gyro))
        return rc_norm, gyro_norm
