import os
import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QComboBox, QFormLayout, QPushButton,
    QStackedWidget, QTextEdit, QSlider, QTabWidget, QSplitter
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg
from fpv_tuner.analysis.noise import (
    calculate_psd, calculate_spectrogram, calculate_signal_stats,
    calculate_throttle_noise_heatmap,
    calculate_pre_post_filter_psd, calculate_pre_post_filter_spectrogram
)
from fpv_tuner.analysis.utils import apply_smoothing
from fpv_tuner.analysis.harmonics import compute_motor_harmonics


def _make_thermal_colormap():
    """Create a thermal/heat colormap (black → red → orange → yellow → white)."""
    positions = [0.0, 0.25, 0.5, 0.75, 1.0]
    colors = [
        (0, 0, 0),        # black
        (128, 0, 0),      # dark red
        (255, 100, 0),    # orange
        (255, 255, 0),    # yellow
        (255, 255, 255),  # white
    ]
    return pg.ColorMap(positions, colors)


class NoiseTab(QWidget):
    SIGNAL_MAP = {
        "Gyro (Filtered) - Roll": ['gyroADC[0]'],
        "Gyro (Filtered) - Pitch": ['gyroADC[1]'],
        "Gyro (Filtered) - Yaw": ['gyroADC[2]'],
        "Gyro (Raw) - Roll": ['gyroUnfilt[0]'],
        "Gyro (Raw) - Pitch": ['gyroUnfilt[1]'],
        "Gyro (Raw) - Yaw": ['gyroUnfilt[2]'],
        "D-Term - Roll": ['dTerm[0]', 'axisD[0]'],
        "D-Term - Pitch": ['dTerm[1]', 'axisD[1]'],
        "D-Term - Yaw": ['dTerm[2]', 'axisD[2]'],
        "Motor 1": ['motor[0]'],
        "Motor 2": ['motor[1]'],
        "Motor 3": ['motor[2]'],
        "Motor 4": ['motor[3]'],
    }
    PLOT_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
    THROTTLE_COLS = ['rcCommand[3]', 'throttle', 'motor[0]']

    def __init__(self):
        super().__init__()
        self.logs = {}

        main_layout = QHBoxLayout(self)
        controls_layout = QVBoxLayout()
        plots_layout = QVBoxLayout()
        main_layout.addLayout(controls_layout, 1)
        main_layout.addLayout(plots_layout, 4)

        # ─── Controls ───
        nperseg_layout = QFormLayout()
        self.nperseg_combo = QComboBox()
        self.nperseg_combo.addItems(["256", "512", "1024", "2048", "4096"])
        self.nperseg_combo.setCurrentText("1024")
        nperseg_layout.addRow("PSD/DSA Resolution:", self.nperseg_combo)

        from PyQt6.QtWidgets import QSpinBox
        self.poles_spin = QSpinBox()
        self.poles_spin.setRange(2, 32)
        self.poles_spin.setSingleStep(2)
        self.poles_spin.setValue(14)
        self.poles_spin.setToolTip("Motor poles. Needed to calculate true mechanical harmonics from eRPM.")
        nperseg_layout.addRow("Motor Poles:", self.poles_spin)

        controls_layout.addLayout(nperseg_layout)

        smoothing_layout = QHBoxLayout()
        smoothing_layout.addWidget(QLabel("Smoothing:"))
        self.smoothing_slider = QSlider(Qt.Orientation.Horizontal)
        self.smoothing_slider.setRange(0, 20)
        self.smoothing_slider.setValue(0)
        self.smoothing_slider.setTickInterval(5)
        self.smoothing_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.smoothing_label = QLabel("Raw")
        smoothing_layout.addWidget(self.smoothing_slider)
        smoothing_layout.addWidget(self.smoothing_label)
        controls_layout.addLayout(smoothing_layout)

        controls_layout.addWidget(QLabel("Signals:"))
        self.signal_list = QListWidget()
        for signal_name in self.SIGNAL_MAP.keys():
            item = QListWidgetItem(signal_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if "Gyro (Filtered) - Roll" in signal_name:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
            self.signal_list.addItem(item)
        controls_layout.addWidget(self.signal_list)

        controls_layout.addWidget(QLabel("Signal Statistics:"))
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setFontFamily("monospace")
        self.stats_text.setFixedHeight(120)
        controls_layout.addWidget(self.stats_text)
        controls_layout.addStretch()

        # ─── Sub-tabbed analysis views ───
        self.analysis_tabs = QTabWidget()

        # ─ Tab 1: PSD + Trace ─
        psd_widget = QWidget()
        psd_layout = QVBoxLayout(psd_widget)
        self.trace_plot = pg.PlotWidget(title="Time Series Trace")
        self.trace_plot.addLegend()
        self.trace_plot.setDownsampling(auto=True, mode='peak')
        self.trace_plot.setClipToView(True)
        self.trace_plot.setLabel('bottom', 'Time (s)')

        self.psd_plot = pg.PlotWidget(title="Power Spectral Density")
        self.psd_plot.addLegend()
        self.psd_plot.setLogMode(x=True, y=True)
        self.psd_plot.setLabel('bottom', 'Frequency (Hz)')
        self.psd_plot.setLabel('left', 'Power (dB/Hz)')
        self.psd_plot.showGrid(x=True, y=True, alpha=0.3)

        psd_layout.addWidget(self.trace_plot)
        psd_layout.addWidget(self.psd_plot)
        self.analysis_tabs.addTab(psd_widget, "📈 PSD")

        # ─ Tab 2: Spectrogram (DSA) ─
        spec_widget = QWidget()
        spec_layout = QVBoxLayout(spec_widget)
        self.spec_trace_plot = pg.PlotWidget(title="Time Series Trace")
        self.spec_trace_plot.addLegend()
        self.spec_trace_plot.setDownsampling(auto=True, mode='peak')
        self.spec_trace_plot.setClipToView(True)
        self.spec_trace_plot.setLabel('bottom', 'Time (s)')

        spectrogram_plot_item = pg.PlotItem()
        spectrogram_plot_item.setLabel('bottom', 'Time (s)')
        spectrogram_plot_item.setLabel('left', 'Frequency (Hz)')
        self.spectrogram_view = pg.ImageView(view=spectrogram_plot_item)
        self.spectrogram_view.setColorMap(_make_thermal_colormap())

        spec_layout.addWidget(self.spec_trace_plot)
        spec_layout.addWidget(self.spectrogram_view)
        self.analysis_tabs.addTab(spec_widget, "🌈 Spectrogram")

        # ─ Tab 3: Throttle vs Noise Heatmap ─
        heatmap_widget = QWidget()
        heatmap_layout = QVBoxLayout(heatmap_widget)

        # Axis selector for heatmap
        hm_controls = QHBoxLayout()
        hm_controls.addWidget(QLabel("Signal:"))
        self.heatmap_signal_combo = QComboBox()
        self.heatmap_signal_combo.addItems([
            "Gyro (Filtered) - Roll", "Gyro (Filtered) - Pitch", "Gyro (Filtered) - Yaw",
            "Gyro (Raw) - Roll", "Gyro (Raw) - Pitch", "Gyro (Raw) - Yaw",
            "D-Term - Roll", "D-Term - Pitch", "D-Term - Yaw",
        ])
        hm_controls.addWidget(self.heatmap_signal_combo)
        hm_controls.addWidget(QLabel("Throttle Src:"))
        self.throttle_src_combo = QComboBox()
        self.throttle_src_combo.addItems(["rcCommand[3]", "Avg Motors"])
        hm_controls.addWidget(self.throttle_src_combo)
        hm_controls.addStretch()
        heatmap_layout.addLayout(hm_controls)

        heatmap_plot_item = pg.PlotItem()
        heatmap_plot_item.setLabel('bottom', 'Throttle (%)')
        heatmap_plot_item.setLabel('left', 'Frequency (Hz)')
        heatmap_plot_item.setTitle('Throttle vs Noise Heatmap')

        self.heatmap_view = pg.ImageView(view=heatmap_plot_item)
        self.heatmap_view.setColorMap(_make_thermal_colormap())
        self.heatmap_view.ui.histogram.hide()
        self.heatmap_view.ui.roiBtn.hide()
        self.heatmap_view.ui.menuBtn.hide()

        # CRITICAL: Override ImageView's destructive defaults AFTER construction
        self.heatmap_view.getView().setAspectLocked(False)
        self.heatmap_view.getView().invertY(False)

        heatmap_layout.addWidget(self.heatmap_view)
        self.analysis_tabs.addTab(heatmap_widget, "🔥 Throttle vs Noise")

        # ─ Tab 4: Pre/Post Filter Comparison ─
        filter_widget = QWidget()
        filter_layout = QVBoxLayout(filter_widget)

        filter_controls = QHBoxLayout()
        filter_controls.addWidget(QLabel("Axis:"))
        self.filter_axis_combo = QComboBox()
        self.filter_axis_combo.addItems(["Roll", "Pitch", "Yaw"])
        filter_controls.addWidget(self.filter_axis_combo)
        filter_controls.addStretch()
        filter_layout.addLayout(filter_controls)

        # PSD comparison plot
        self.filter_psd_plot = pg.PlotWidget(title="Pre-Filter vs Post-Filter PSD")
        self.filter_psd_plot.addLegend()
        self.filter_psd_plot.setLogMode(x=True, y=True)
        self.filter_psd_plot.setLabel('bottom', 'Frequency (Hz)')
        self.filter_psd_plot.setLabel('left', 'Power (dB/Hz)')
        self.filter_psd_plot.showGrid(x=True, y=True, alpha=0.3)
        filter_layout.addWidget(self.filter_psd_plot)

        # Spectrogram comparison: pre and post side by side
        spec_compare_layout = QHBoxLayout()

        pre_spec_item = pg.PlotItem()
        pre_spec_item.setLabel('bottom', 'Time (s)')
        pre_spec_item.setLabel('left', 'Frequency (Hz)')
        pre_spec_item.setTitle('Pre-Filter (Raw)')
        self.pre_filter_spec = pg.ImageView(view=pre_spec_item)
        self.pre_filter_spec.setColorMap(_make_thermal_colormap())
        spec_compare_layout.addWidget(self.pre_filter_spec)

        post_spec_item = pg.PlotItem()
        post_spec_item.setLabel('bottom', 'Time (s)')
        post_spec_item.setLabel('left', 'Frequency (Hz)')
        post_spec_item.setTitle('Post-Filter')
        self.post_filter_spec = pg.ImageView(view=post_spec_item)
        self.post_filter_spec.setColorMap(_make_thermal_colormap())
        spec_compare_layout.addWidget(self.post_filter_spec)

        filter_layout.addLayout(spec_compare_layout)
        self.analysis_tabs.addTab(filter_widget, "🛡️ Filter Analysis")

        # ─ Tab 5: Compare Iterations ─
        compare_widget = QWidget()
        compare_layout = QVBoxLayout(compare_widget)
        
        comp_controls = QHBoxLayout()
        comp_controls.addWidget(QLabel("Signal:"))
        self.comp_signal_combo = QComboBox()
        self.comp_signal_combo.addItems(list(self.SIGNAL_MAP.keys()))
        self.comp_signal_combo.setCurrentText("Gyro (Filtered) - Roll")
        comp_controls.addWidget(self.comp_signal_combo)
        comp_controls.addStretch()
        compare_layout.addLayout(comp_controls)

        self.comp_psd_plot = pg.PlotWidget(title="Compare PSD: Before vs After")
        self.comp_psd_plot.addLegend()
        self.comp_psd_plot.setLogMode(x=True, y=True)
        self.comp_psd_plot.setLabel('bottom', 'Frequency (Hz)')
        self.comp_psd_plot.setLabel('left', 'Power (dB/Hz)')
        self.comp_psd_plot.showGrid(x=True, y=True, alpha=0.3)
        compare_layout.addWidget(self.comp_psd_plot)

        self.analysis_tabs.addTab(compare_widget, "📊 Compare Iterations")

        plots_layout.addWidget(self.analysis_tabs)

        # ─── Connections ───
        self.nperseg_combo.currentTextChanged.connect(self.update_plots)
        self.poles_spin.valueChanged.connect(self.update_plots)
        self.signal_list.itemChanged.connect(self.update_plots)
        self.smoothing_slider.valueChanged.connect(self.on_smoothing_changed)
        self.heatmap_signal_combo.currentTextChanged.connect(self.update_plots)
        self.throttle_src_combo.currentTextChanged.connect(self.update_plots)
        self.filter_axis_combo.currentTextChanged.connect(self.update_plots)
        self.comp_signal_combo.currentTextChanged.connect(self.update_plots)
        self.analysis_tabs.currentChanged.connect(self.update_plots)

    def on_smoothing_changed(self, value):
        self.smoothing_label.setText("Raw" if value == 0 else f"Level {value}")
        self.update_plots()

    def set_data(self, logs):
        self.logs = logs
        self.update_plots()

    def update_plots(self):
        if not self.logs:
            return

        current_tab = self.analysis_tabs.currentIndex()
        if current_tab == 0:
            self._update_psd_view()
        elif current_tab == 1:
            self._update_spectrogram_view()
        elif current_tab == 2:
            self._update_throttle_heatmap()
        elif current_tab == 3:
            self._update_filter_analysis()
        elif current_tab == 4:
            self._update_compare_tab()

    # ─── PSD View ───
    def _update_psd_view(self):
        self.trace_plot.clear()
        self.psd_plot.clear()
        self.stats_text.clear()

        checked = self._get_checked_signals()
        if not checked:
            return

        nperseg = int(self.nperseg_combo.currentText())
        df = self._get_first_df()
        if df is None:
            return

        time_col = self._find_column(df, ['time (us)', 'time'])
        if not time_col:
            return
        time_us = df[time_col]
        time_s = time_us / 1_000_000

        full_stats = ""
        for i, signal_name in enumerate(checked):
            col_name = self._find_column(df, self.SIGNAL_MAP.get(signal_name, []))
            if not col_name:
                continue

            color = self.PLOT_COLORS[i % len(self.PLOT_COLORS)]
            pen = pg.mkPen(color=color, width=1)

            signal_data = df[col_name]
            smoothed = apply_smoothing(signal_data, self.smoothing_slider.value())
            self.trace_plot.plot(time_s, smoothed, pen=pen, name=signal_name)

            freq, psd = calculate_psd(signal_data, time_us, nperseg=nperseg)
            stats = {}
            if freq is not None and psd is not None and len(freq) > 0:
                psd_db = 10 * np.log10(psd + 1e-12)
                self.psd_plot.plot(freq, psd_db, pen=pen, name=signal_name)
                stats = calculate_signal_stats(signal_data, freq, psd)
            else:
                stats = calculate_signal_stats(signal_data, None, None)

            full_stats += f"── {signal_name} ──\n"
            for k, v in stats.items():
                full_stats += f"  {k}: {v}\n"
            full_stats += "\n"

        self.stats_text.setText(full_stats)

        # Overlay motor harmonics (if available)
        motor_poles = self.poles_spin.value()
        harmonics_df = compute_motor_harmonics(df, motor_poles, time_col)
        if harmonics_df is not None:
            for label, col, color in [("H1", "h1_hz", "#ff5555"),
                                      ("H2", "h2_hz", "#ffaa55"),
                                      ("H3", "h3_hz", "#ffff55")]:
                freq_median = harmonics_df[col].median()
                if pd.notna(freq_median):
                    line = pg.InfiniteLine(
                        pos=freq_median, angle=90,
                        pen=pg.mkPen(color, style=Qt.PenStyle.DashLine)
                    )
                    # Cannot set tooltip on line easily in older pyqtgraph, we just add it
                    self.psd_plot.addItem(line)

    # ─── Spectrogram View ───
    def _update_spectrogram_view(self):
        self.spec_trace_plot.clear()
        self.spectrogram_view.clear()

        checked = self._get_checked_signals()
        if not checked:
            return

        nperseg = int(self.nperseg_combo.currentText())
        df = self._get_first_df()
        if df is None:
            return

        time_col = self._find_column(df, ['time (us)', 'time'])
        if not time_col:
            return
        time_us = df[time_col]
        time_s = time_us / 1_000_000

        # Plot all checked traces
        for i, signal_name in enumerate(checked):
            col_name = self._find_column(df, self.SIGNAL_MAP.get(signal_name, []))
            if col_name:
                color = self.PLOT_COLORS[i % len(self.PLOT_COLORS)]
                smoothed = apply_smoothing(df[col_name], self.smoothing_slider.value())
                self.spec_trace_plot.plot(time_s, smoothed, pen=pg.mkPen(color=color), name=signal_name)

        # Spectrogram for first signal
        signal_name = checked[0]
        col_name = self._find_column(df, self.SIGNAL_MAP.get(signal_name, []))
        if not col_name:
            return

        freqs, times, Sxx = calculate_spectrogram(df[col_name], time_us, nperseg=nperseg)
        if freqs is not None and times is not None and Sxx is not None:
            Sxx_log = np.log10(Sxx + 1e-12)
            tr = pg.QtGui.QTransform()
            tr.scale(times[-1] / Sxx.shape[1], freqs[-1] / Sxx.shape[0])
            self.spectrogram_view.setImage(Sxx_log.T, autoRange=False, transform=tr)
            self.spectrogram_view.getView().setTitle(f"Spectrogram — {signal_name}")

    # ─── Throttle vs Noise Heatmap ───
    def _update_throttle_heatmap(self):
        self.heatmap_view.clear()

        df = self._get_first_df()
        if df is None:
            return

        time_col = self._find_column(df, ['time (us)', 'time'])
        if not time_col:
            return

        # Get noise signal
        signal_name = self.heatmap_signal_combo.currentText()
        noise_col = self._find_column(df, self.SIGNAL_MAP.get(signal_name, []))
        if not noise_col:
            return

        # Get throttle
        throttle_src = self.throttle_src_combo.currentText()
        throttle_data = None

        def _normalize_to_pct(series):
            """Safely normalize a series to 0-100 range, handling constant values."""
            mn, mx = series.min(), series.max()
            if mx > mn:
                return (series - mn) / (mx - mn) * 100.0
            # Constant value: map to a fixed percentage
            return pd.Series(np.full(len(series), 50.0), index=series.index)

        if throttle_src == "Avg Motors":
            motor_cols = [f'motor[{i}]' for i in range(4)]
            available = [c for c in motor_cols if c in df.columns]
            if available:
                motor_avg = df[available].mean(axis=1)
                throttle_data = _normalize_to_pct(motor_avg)
        else:
            throttle_col = self._find_column(df, ['rcCommand[3]', 'throttle'])
            if throttle_col:
                raw_throttle = df[throttle_col]
                if raw_throttle.max() > 1000:
                    throttle_data = (raw_throttle - 1000) / 1000.0 * 100.0
                    throttle_data = throttle_data.clip(0, 100)
                else:
                    throttle_data = _normalize_to_pct(raw_throttle).astype(float)

        if throttle_data is None:
            return

        nperseg = int(self.nperseg_combo.currentText())
        throttle_centers, freq_bins, heatmap = calculate_throttle_noise_heatmap(
            df[noise_col], throttle_data, df[time_col],
            n_throttle_bins=80, n_freq_bins=256, nperseg=nperseg
        )

        if throttle_centers is None or heatmap is None:
            return

        # Set up the image with correct axis scaling
        img = heatmap.T  # shape: (n_throttle, n_freq) -> pyqtgraph X=throttle, Y=freq
        freq_max = freq_bins[-1]
        
        tr = pg.QtGui.QTransform()
        tr.scale(100.0 / img.shape[0], freq_max / img.shape[1])
        self.heatmap_view.setImage(img, autoRange=False, transform=tr)
        
        self.heatmap_view.getView().setLimits(xMin=0, xMax=100, yMin=0, yMax=freq_max)
        self.heatmap_view.getView().setXRange(0, 100, padding=0)
        self.heatmap_view.getView().setYRange(0, freq_max, padding=0)
        self.heatmap_view.getView().setTitle(f"Throttle vs Noise — {signal_name}")
        
        x_ax = self.heatmap_view.getView().getAxis("bottom")
        x_ax.setTicks([[(i, str(i)) for i in range(0, 101, 20)]])
        y_ax = self.heatmap_view.getView().getAxis("left")
        y_ax.setTicks([[(i, str(i)) for i in range(0, int(freq_max) + 1, 200)]])

        # Overlay Harmonic Curve
        motor_poles = self.poles_spin.value()
        harmonics_df = compute_motor_harmonics(df, motor_poles, time_col)
        if harmonics_df is not None:
            # We must map harmonics_df['h1_hz'] against throttle_centers.
            # Interpolating throttle vs h1_hz.
            valid_idx = throttle_data.notna() & harmonics_df['h1_hz'].notna()
            t_data_clean = throttle_data[valid_idx].values
            h1_clean = harmonics_df['h1_hz'][valid_idx].values
            
            if len(t_data_clean) > 0:
                sort_idx = np.argsort(t_data_clean)
                t_sorted = t_data_clean[sort_idx]
                h1_sorted = h1_clean[sort_idx]
                binned_h1 = np.interp(throttle_centers, t_sorted, h1_sorted)
                
                curve = pg.PlotCurveItem(throttle_centers, binned_h1,
                                         pen=pg.mkPen('#00ffff', width=2, style=Qt.PenStyle.DashLine))
                self.heatmap_view.getView().addItem(curve)

    # ─── Pre/Post Filter Analysis ───
    def _update_filter_analysis(self):
        self.filter_psd_plot.clear()
        self.pre_filter_spec.clear()
        self.post_filter_spec.clear()

        df = self._get_first_df()
        if df is None:
            return

        time_col = self._find_column(df, ['time (us)', 'time'])
        if not time_col:
            return

        axis_map = {"Roll": 0, "Pitch": 1, "Yaw": 2}
        axis_idx = axis_map.get(self.filter_axis_combo.currentText(), 0)
        nperseg = int(self.nperseg_combo.currentText())

        # ── PSD comparison ──
        psd_result = calculate_pre_post_filter_psd(df, time_col, axis_idx, nperseg=nperseg)
        if psd_result:
            freq = psd_result.get('freq')
            if freq is not None:
                if 'psd_pre' in psd_result:
                    psd_db = 10 * np.log10(psd_result['psd_pre'] + 1e-12)
                    self.filter_psd_plot.plot(freq, psd_db,
                                              pen=pg.mkPen('#ff4444', width=2),
                                              name='Pre-Filter (Raw)')
                if 'psd_post' in psd_result:
                    psd_db = 10 * np.log10(psd_result['psd_post'] + 1e-12)
                    self.filter_psd_plot.plot(freq, psd_db,
                                              pen=pg.mkPen('#44ff44', width=2),
                                              name='Post-Filter')

        # ── Spectrogram comparison ──
        spec_result = calculate_pre_post_filter_spectrogram(df, time_col, axis_idx, nperseg=nperseg)
        if spec_result:
            freqs = spec_result.get('freqs')
            times = spec_result.get('times')
            if freqs is not None and times is not None:
                if 'Sxx_pre' in spec_result:
                    Sxx_log = np.log10(spec_result['Sxx_pre'] + 1e-12)
                    tr = pg.QtGui.QTransform()
                    tr.scale(times[-1] / spec_result['Sxx_pre'].shape[1],
                             freqs[-1] / spec_result['Sxx_pre'].shape[0])
                    self.pre_filter_spec.setImage(Sxx_log.T, autoRange=False, transform=tr)

                if 'Sxx_post' in spec_result:
                    Sxx_log = np.log10(spec_result['Sxx_post'] + 1e-12)
                    tr = pg.QtGui.QTransform()
                    tr.scale(times[-1] / spec_result['Sxx_post'].shape[1],
                             freqs[-1] / spec_result['Sxx_post'].shape[0])
                    self.post_filter_spec.setImage(Sxx_log.T, autoRange=False, transform=tr)

    # ─── Compare Iterations ───
    def _update_compare_tab(self):
        self.comp_psd_plot.clear()
        
        if len(self.logs) < 2:
            return  # Need at least two logs
            
        log_ids = list(self.logs.keys())
        df_before = self.logs[log_ids[-2]].get('df')
        df_after = self.logs[log_ids[-1]].get('df')
        
        if df_before is None or df_after is None:
            return
            
        time_col_before = self._find_column(df_before, ['time (us)', 'time'])
        time_col_after = self._find_column(df_after, ['time (us)', 'time'])
        if not time_col_before or not time_col_after:
            return

        signal_name = self.comp_signal_combo.currentText()
        col_before = self._find_column(df_before, self.SIGNAL_MAP.get(signal_name, []))
        col_after = self._find_column(df_after, self.SIGNAL_MAP.get(signal_name, []))
        
        nperseg = int(self.nperseg_combo.currentText())

        if col_before:
            f_before, p_before = calculate_psd(df_before[col_before], df_before[time_col_before], nperseg=nperseg)
            if f_before is not None and len(f_before) > 0:
                p_db_before = 10 * np.log10(p_before + 1e-12)
                pen_before = pg.mkPen(color='#888888', width=2, style=Qt.PenStyle.DashLine)
                self.comp_psd_plot.plot(f_before, p_db_before, pen=pen_before, name="Before")

        if col_after:
            f_after, p_after = calculate_psd(df_after[col_after], df_after[time_col_after], nperseg=nperseg)
            if f_after is not None and len(f_after) > 0:
                p_db_after = 10 * np.log10(p_after + 1e-12)
                pen_after = pg.mkPen(color='#00ff00', width=2, style=Qt.PenStyle.SolidLine)
                self.comp_psd_plot.plot(f_after, p_db_after, pen=pen_after, name="After")

    # ─── Helpers ───
    def _get_checked_signals(self):
        return [
            self.signal_list.item(i).text()
            for i in range(self.signal_list.count())
            if self.signal_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _get_first_df(self):
        if not self.logs:
            return None
        _, log_dict = next(iter(self.logs.items()))
        return log_dict.get('df')

    def _find_column(self, df, possible_names):
        for name in possible_names:
            if name in df.columns:
                return name
        return None
