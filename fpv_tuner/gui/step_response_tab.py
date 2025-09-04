import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel
)
import pyqtgraph as pg
from fpv_tuner.analysis.step_response import find_step_responses

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
        controls_layout = QHBoxLayout()
        main_layout.addLayout(controls_layout)

        self.plot_widget = pg.PlotWidget(title="Step Response")
        self.plot_widget.addLegend()
        self.plot_widget.setDownsampling(auto=True, mode='peak')
        self.plot_widget.setClipToView(True)
        main_layout.addWidget(self.plot_widget)

        controls_layout.addWidget(QLabel("Log File:"))
        self.log_combo = QComboBox()
        self.log_combo.currentTextChanged.connect(self.on_log_selection_change)
        controls_layout.addWidget(self.log_combo)

        controls_layout.addWidget(QLabel("Axis:"))
        self.axis_combo = QComboBox()
        self.axis_combo.addItems(self.AXES_MAP.keys())
        self.axis_combo.currentTextChanged.connect(self.analyze_axis)
        controls_layout.addWidget(self.axis_combo)

        self.prev_button = QPushButton("<< Previous")
        self.prev_button.clicked.connect(self.prev_step)
        controls_layout.addWidget(self.prev_button)

        self.step_label = QLabel("No steps found")
        controls_layout.addWidget(self.step_label)

        self.next_button = QPushButton("Next >>")
        self.next_button.clicked.connect(self.next_step)
        controls_layout.addWidget(self.next_button)
        controls_layout.addStretch()

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

        if rc_col and time_col:
            self.steps = find_step_responses(log_data[rc_col], log_data[time_col])

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

        time_us = self._find_column(log_data, ['time (us)', 'time'])
        if time_us is None: return
        time_s = log_data[time_us] / 1_000_000

        self.plot_widget.addItem(pg.InfiniteLine(pos=time_s.iloc[step_idx], angle=90, movable=False, pen='gray'))

        data_window = log_data.iloc[start:end]
        time_window = time_s.iloc[start:end]

        setpoint_col = self._find_column(log_data, [cols["setpoint"]])
        gyro_col = self._find_column(log_data, [cols["gyro"]])
        dterm_col = self._find_column(log_data, cols["dterm"]) # Corrected call

        if setpoint_col:
            self.plot_widget.plot(time_window, data_window[setpoint_col], pen='c', name='Setpoint')
        if gyro_col:
            self.plot_widget.plot(time_window, data_window[gyro_col], pen='y', name='Gyro')
        if dterm_col:
            self.plot_widget.plot(time_window, data_window[dterm_col], pen='m', name='D-Term')

    def _find__column(self, df, possible_names):
        for name in possible_names:
            if name in df.columns:
                return name
        return None
