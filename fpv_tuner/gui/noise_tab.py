import os
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QComboBox, QGridLayout, QLabel
)
import pyqtgraph as pg
from fpv_tuner.analysis.noise import calculate_psd

class NoiseTab(QWidget):
    DATA_SOURCES = {
        "Gyro (Raw)": {
            "roll": ['gyroADC[0]', 'gyroUnfilt[0]'],
            "pitch": ['gyroADC[1]', 'gyroUnfilt[1]'],
            "yaw": ['gyroADC[2]', 'gyroUnfilt[2]'],
        },
        "Gyro (Filtered)": {
            "roll": ['gyroData[0]'],
            "pitch": ['gyroData[1]'],
            "yaw": ['gyroData[2]'],
        },
        "D-Term": {
            "roll": ['dTerm[0]', 'axisD[0]'],
            "pitch": ['dTerm[1]', 'axisD[1]'],
            "yaw": ['dTerm[2]', 'axisD[2]'],
        }
    }
    AXES = ["roll", "pitch", "yaw"]
    PLOT_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    def __init__(self):
        super().__init__()
        self.logs = {}

        main_layout = QHBoxLayout(self)
        controls_layout = QVBoxLayout()
        plots_layout = QVBoxLayout()
        main_layout.addLayout(controls_layout, 1)
        main_layout.addLayout(plots_layout, 3)

        controls_layout.addWidget(QLabel("Data Source:"))
        self.source_combo = QComboBox()
        self.source_combo.addItems(self.DATA_SOURCES.keys())
        self.source_combo.currentTextChanged.connect(self.update_plots)
        controls_layout.addWidget(self.source_combo)

        controls_layout.addWidget(QLabel("Axes:"))
        self.axis_checkboxes = {}
        for axis in self.AXES:
            self.axis_checkboxes[axis] = QCheckBox(axis.capitalize())
            self.axis_checkboxes[axis].setChecked(True)
            self.axis_checkboxes[axis].stateChanged.connect(self.update_plots)
            controls_layout.addWidget(self.axis_checkboxes[axis])

        controls_layout.addStretch()

        self.trace_plot = pg.PlotWidget(title="Time Series Trace")
        self.psd_plot = pg.PlotWidget(title="Power Spectral Density (PSD)")
        self.trace_plot.addLegend()
        self.psd_plot.addLegend()
        self.trace_plot.setDownsampling(auto=True, mode='peak')
        self.trace_plot.setClipToView(True)
        self.psd_plot.setLogMode(x=True, y=True)
        self.psd_plot.setLabel('bottom', 'Frequency (Hz)')
        self.psd_plot.setLabel('left', 'Power/Frequency (dB/Hz)')
        plots_layout.addWidget(self.trace_plot)
        plots_layout.addWidget(self.psd_plot)

    def set_data(self, logs):
        self.logs = logs
        self.update_plots()

    def update_plots(self):
        self.trace_plot.clear()
        self.psd_plot.clear()
        if not self.logs:
            return

        source_key = self.source_combo.currentText()

        for i, (filename, log_data) in enumerate(self.logs.items()):
            color_set = self.PLOT_COLORS[i % len(self.PLOT_COLORS)]
            short_name = os.path.basename(filename)

            time_col = self._find_column(log_data, ['time (us)', 'time'])
            if not time_col:
                continue

            time_us = log_data[time_col]
            time_s = time_us / 1_000_000

            for axis_name in self.AXES:
                if self.axis_checkboxes[axis_name].isChecked():
                    possible_names = self.DATA_SOURCES[source_key][axis_name]
                    col_name = self._find_column(log_data, possible_names)

                    if col_name:
                        pen = pg.mkPen(color=color_set, style=pg.QtCore.Qt.PenStyle.SolidLine)

                        self.trace_plot.plot(time_s, log_data[col_name], pen=pen, name=f"{short_name} - {axis_name}")

                        freq, psd = calculate_psd(log_data[col_name], time_us)
                        if freq is not None and len(freq) > 0 and psd is not None and len(psd) > 0:
                            psd_db = 10 * np.log10(psd)
                            self.psd_plot.plot(freq, psd_db, pen=pen, name=f"{short_name} - {axis_name} PSD")

    def _find_column(self, df, possible_names):
        for name in possible_names:
            if name in df.columns:
                return name
        return None
