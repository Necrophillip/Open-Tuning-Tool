import os
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QListWidget, QListWidgetItem, QComboBox, QFormLayout, QPushButton,
    QStackedWidget, QTextEdit
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg
from fpv_tuner.analysis.noise import calculate_psd, calculate_spectrogram, calculate_signal_stats

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
        self.is_psd_mode = True

        main_layout = QHBoxLayout(self)
        controls_layout = QVBoxLayout()
        plots_layout = QVBoxLayout()
        main_layout.addLayout(controls_layout, 1)
        main_layout.addLayout(plots_layout, 3)

        # --- Controls ---
        nperseg_layout = QFormLayout()
        self.nperseg_combo = QComboBox()
        self.nperseg_combo.addItems(["256", "512", "1024", "2048", "4096"])
        self.nperseg_combo.setCurrentText("1024")
        nperseg_layout.addRow("PSD/DSA Resolution:", self.nperseg_combo)
        controls_layout.addLayout(nperseg_layout)

        self.view_toggle_button = QPushButton("Show Spectrogram (DSA)")
        controls_layout.addWidget(self.view_toggle_button)

        controls_layout.addWidget(QLabel("Signals:"))
        self.signal_list = QListWidget()
        for signal_name in self.SIGNAL_MAP.keys():
            item = QListWidgetItem(signal_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if "Gyro (Raw) - Roll" in signal_name:
                 item.setCheckState(Qt.CheckState.Checked)
            else:
                 item.setCheckState(Qt.CheckState.Unchecked)
            self.signal_list.addItem(item)

        controls_layout.addWidget(self.signal_list)

        controls_layout.addWidget(QLabel("Signal Statistics (PSD Mode):"))
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setFontFamily("monospace")
        self.stats_text.setFixedHeight(100)
        controls_layout.addWidget(self.stats_text)
        controls_layout.addStretch()

        # --- Plots ---
        self.trace_plot = pg.PlotWidget(title="Time Series Trace")
        self.trace_plot.addLegend()
        self.trace_plot.setDownsampling(auto=True, mode='peak')
        self.trace_plot.setClipToView(True)

        self.psd_plot = pg.PlotWidget(title="Power Spectral Density (PSD)")
        self.psd_plot.addLegend()
        self.psd_plot.setLogMode(x=True, y=True)
        self.psd_plot.setLabel('bottom', 'Frequency (Hz)')
        self.psd_plot.setLabel('left', 'Power/Frequency (dB/Hz)')

        spectrogram_plot_item = pg.PlotItem()
        spectrogram_plot_item.setLabel('bottom', 'Time (s)')
        spectrogram_plot_item.setLabel('left', 'Frequency (Hz)')
        self.spectrogram_view = pg.ImageView(view=spectrogram_plot_item)

        self.plot_stack = QStackedWidget()
        self.plot_stack.addWidget(self.psd_plot)
        self.plot_stack.addWidget(self.spectrogram_view)

        plots_layout.addWidget(self.trace_plot)
        plots_layout.addWidget(self.plot_stack)

        # --- Connections ---
        self.nperseg_combo.currentTextChanged.connect(self.update_plots)
        self.signal_list.itemChanged.connect(self.update_plots)
        self.view_toggle_button.clicked.connect(self.on_toggle_view_clicked)

    def set_data(self, logs):
        self.logs = logs
        self.update_plots()

    def update_plots(self):
        # Clear all plots and stats first
        self.trace_plot.clear()
        self.psd_plot.clear()
        self.spectrogram_view.clear()
        self.stats_text.clear()

        if not self.logs:
            return

        checked_signals = [self.signal_list.item(i).text() for i in range(self.signal_list.count()) if self.signal_list.item(i).checkState() == Qt.CheckState.Checked]

        if not checked_signals:
            return

        nperseg = int(self.nperseg_combo.currentText())
        filename, log_data = next(iter(self.logs.items()))

        time_col = self._find_column(log_data, ['time (us)', 'time'])
        if not time_col:
            return
        time_us = log_data[time_col]
        time_s = time_us / 1_000_000

        # --- PSD Mode ---
        if self.is_psd_mode:
            self.trace_plot.addLegend()
            self.psd_plot.addLegend()
            full_stats_text = ""
            for i, signal_name in enumerate(checked_signals):
                possible_names = self.SIGNAL_MAP.get(signal_name)
                if not possible_names: continue

                col_name = self._find_column(log_data, possible_names)
                if col_name:
                    color = self.PLOT_COLORS[i % len(self.PLOT_COLORS)]
                    pen = pg.mkPen(color=color)
                    signal_data = log_data[col_name]

                    self.trace_plot.plot(time_s, signal_data, pen=pen, name=signal_name)
                    freq, psd = calculate_psd(signal_data, time_us, nperseg=nperseg)

                    stats = {}
                    if freq is not None and psd is not None and len(freq) > 0 and len(psd) > 0:
                        psd_db = 10 * np.log10(psd + 1e-12)
                        self.psd_plot.plot(freq, psd_db, pen=pen, name=f"{signal_name} PSD")
                        stats = calculate_signal_stats(signal_data, freq, psd)
                    else:
                        stats = calculate_signal_stats(signal_data, None, None)

                    full_stats_text += f"--- {signal_name} ---\n"
                    for key, value in stats.items():
                        full_stats_text += f"  {key}: {value}\n"
                    full_stats_text += "\n"

            self.stats_text.setText(full_stats_text)

        # --- Spectrogram Mode ---
        else:
            self.trace_plot.addLegend(None) # Hide legend
            self.psd_plot.clear()

            # Use first selected signal for spectrogram
            signal_name = checked_signals[0]
            possible_names = self.SIGNAL_MAP.get(signal_name)
            if not possible_names: return

            col_name = self._find_column(log_data, possible_names)
            if col_name:
                signal_data = log_data[col_name]
                self.trace_plot.plot(time_s, signal_data, pen='w', name=signal_name)

                freqs, times, Sxx = calculate_spectrogram(signal_data, time_us, nperseg=nperseg)

                if freqs is not None and times is not None and Sxx is not None:
                    # Log scale for better color visualization
                    Sxx_log = np.log10(Sxx + 1e-12) # Add epsilon to avoid log(0)

                    # pyqtgraph ImageView needs a transform to set the axes scales correctly
                    tr = pg.QtGui.QTransform()
                    tr.scale(times[-1] / Sxx.shape[1], freqs[-1] / Sxx.shape[0])
                    self.spectrogram_view.setImage(Sxx_log.T, autoRange=False, transform=tr)
                    self.spectrogram_view.getView().setTitle(f"Spectrogram - {signal_name}")

    def on_toggle_view_clicked(self):
        self.is_psd_mode = not self.is_psd_mode
        if self.is_psd_mode:
            self.plot_stack.setCurrentWidget(self.psd_plot)
            self.view_toggle_button.setText("Show Spectrogram (DSA)")
            self.stats_text.setVisible(True)
        else:
            self.plot_stack.setCurrentWidget(self.spectrogram_view)
            self.view_toggle_button.setText("Show PSD")
            self.stats_text.setVisible(False) # Stats are for PSD only

        self.update_plots()

    def _find_column(self, df, possible_names):
        for name in possible_names:
            if name in df.columns:
                return name
        return None
