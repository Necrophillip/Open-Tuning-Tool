import os
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QGridLayout, QLabel,
    QListWidget, QListWidgetItem, QComboBox, QFormLayout
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg
from fpv_tuner.analysis.noise import calculate_psd

class NoiseTab(QWidget):
    SIGNAL_MAP = {
        "Gyro (Raw) - Roll": ['gyroADC[0]', 'gyroUnfilt[0]'],
        "Gyro (Raw) - Pitch": ['gyroADC[1]', 'gyroUnfilt[1]'],
        "Gyro (Raw) - Yaw": ['gyroADC[2]', 'gyroUnfilt[2]'],
        "D-Term - Roll": ['dTerm[0]', 'axisD[0]'],
        "D-Term - Pitch": ['dTerm[1]', 'axisD[1]'],
        "D-Term - Yaw": ['dTerm[2]', 'axisD[2]'],
        "Motor 1": ['motor[0]'],
        "Motor 2": ['motor[1]'],
        "Motor 3": ['motor[2]'],
        "Motor 4": ['motor[3]'],
    }
    PLOT_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    def __init__(self):
        super().__init__()
        self.logs = {}

        main_layout = QHBoxLayout(self)
        controls_layout = QVBoxLayout()
        plots_layout = QVBoxLayout()
        main_layout.addLayout(controls_layout, 1)
        main_layout.addLayout(plots_layout, 3)

        # --- Controls ---
        # nperseg ComboBox
        nperseg_layout = QFormLayout()
        self.nperseg_combo = QComboBox()
        self.nperseg_combo.addItems(["256", "512", "1024", "2048", "4096"])
        self.nperseg_combo.setCurrentText("1024")
        nperseg_layout.addRow("PSD Resolution (NPERSEG):", self.nperseg_combo)
        controls_layout.addLayout(nperseg_layout)

        # Signal List
        controls_layout.addWidget(QLabel("Signals:"))
        self.signal_list = QListWidget()
        for signal_name in self.SIGNAL_MAP.keys():
            item = QListWidgetItem(signal_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            # Default to showing Gyro Roll
            if "Gyro (Raw) - Roll" in signal_name:
                 item.setCheckState(Qt.CheckState.Checked)
            else:
                 item.setCheckState(Qt.CheckState.Unchecked)
            self.signal_list.addItem(item)

        controls_layout.addWidget(self.signal_list)

        # Stats Display
        controls_layout.addWidget(QLabel("Signal Statistics:"))
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setFontFamily("monospace")
        self.stats_text.setFixedHeight(100) # Give it a fixed height
        controls_layout.addWidget(self.stats_text)

        controls_layout.addStretch()

        # --- Connections ---
        self.nperseg_combo.currentTextChanged.connect(self.update_plots)
        self.signal_list.itemChanged.connect(self.update_plots)

        # --- Plots ---
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
        self.stats_text.clear()

        if not self.logs:
            return

        checked_signals = []
        for i in range(self.signal_list.count()):
            item = self.signal_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                checked_signals.append(item.text())

        if not checked_signals:
            return

        nperseg = int(self.nperseg_combo.currentText())

        color_index = 0
        full_stats_text = ""

        filename, log_data = next(iter(self.logs.items()))

        time_col = self._find_column(log_data, ['time (us)', 'time'])
        if not time_col:
            return

        time_us = log_data[time_col]
        time_s = time_us / 1_000_000

        for signal_name in checked_signals:
            possible_names = self.SIGNAL_MAP.get(signal_name)
            if not possible_names:
                continue

            col_name = self._find_column(log_data, possible_names)

            if col_name:
                color = self.PLOT_COLORS[color_index % len(self.PLOT_COLORS)]
                pen = pg.mkPen(color=color, style=Qt.PenStyle.SolidLine)

                signal_data = log_data[col_name]
                self.trace_plot.plot(time_s, signal_data, pen=pen, name=signal_name)

                freq, psd = calculate_psd(signal_data, time_us, nperseg=nperseg)

                stats = {}
                if freq is not None and len(freq) > 0 and psd is not None and len(psd) > 0:
                    psd_db = 10 * np.log10(psd)
                    self.psd_plot.plot(freq, psd_db, pen=pen, name=f"{signal_name} PSD")
                    stats = calculate_signal_stats(signal_data, freq, psd)
                else: # Still calculate time-domain stats even if PSD fails
                    stats = calculate_signal_stats(signal_data, None, None)

                # Format stats for this signal
                full_stats_text += f"--- {signal_name} ---\n"
                for key, value in stats.items():
                    full_stats_text += f"  {key}: {value}\n"
                full_stats_text += "\n"

                color_index += 1

        self.stats_text.setText(full_stats_text)

    def _find_column(self, df, possible_names):
        for name in possible_names:
            if name in df.columns:
                return name
        return None
