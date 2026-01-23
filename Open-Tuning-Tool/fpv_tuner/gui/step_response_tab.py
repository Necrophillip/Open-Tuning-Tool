import os
import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QFormLayout, QTextEdit,
    QPushButton, QLabel, QFileDialog, QDoubleSpinBox, QSpinBox
)
from scipy.signal import savgol_filter
import pyqtgraph as pg
from fpv_tuner.analysis.step_response import analyze_step_response

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

        # Detection threshold and loop frequency controls removed — analyzer is automatic

        controls_layout.addLayout(form_layout)
        controls_layout.addStretch()

        self.log_combo.currentTextChanged.connect(self.run_analysis)
        self.axis_combo.currentTextChanged.connect(self.run_analysis)

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

        # Prefer automatic estimation of loop frequency from timestamps
        try:
            t_us = time_data.astype(float)
            dt = np.diff(t_us)
            median_dt = np.median(dt[dt>0]) if np.any(dt>0) else 1000.0
            est_fs = int(round(1e6 / median_dt)) if median_dt > 0 else self.loop_freq
        except Exception:
            est_fs = self.loop_freq

        # Call the analyzer on the full trace for this axis; analyzer will locate the main step
        try:
            analysis = analyze_step_response(time_data.astype(int), rc_data, gyro_data, pid_loop_hz=est_fs, plot=False)
        except Exception as e:
            self.metrics_text.setText(f"Analysis error: {e}")
            return

        if analysis is None or 'error' in analysis:
            self.metrics_text.setText(f"Analysis failed: {analysis.get('error') if analysis else 'unknown'}")
            return

        # Get fitted curve and metrics
        t_fit = analysis.get('t_fit')
        y_fit = analysis.get('y_fit')
        metrics = analysis.get('metrics', {})
        t_seg = analysis.get('t_segment')
        y_seg = analysis.get('y_segment')

        if t_seg is None or y_seg is None:
            self.metrics_text.setText('Analysis returned no segment data')
            return

        # Get step amplitude from metrics (the analyzer already calculated this correctly)
        step_amp = metrics.get('step_input_amplitude', None)
        y0 = metrics.get('y0', None)  # Initial gyro output baseline
        
        if step_amp is None or np.isclose(step_amp, 0):
            # Fallback: calculate from segment data
            y_seg_arr = np.asarray(y_seg, dtype=float)
            pre_y = np.mean(y_seg_arr[:max(1, 5)])
            post_y = np.mean(y_seg_arr[-max(1, 5):])
            step_amp = np.abs(post_y - pre_y)
            if np.isclose(step_amp, 0):
                step_amp = 1.0
            y0 = pre_y
        
        if y0 is None:
            y0_arr = np.asarray(y_seg, dtype=float)
            y0 = np.mean(y0_arr[:max(1, 5)])

        # Normalize gyro response: subtract pre-step baseline and divide by step amplitude
        # This ensures: pre-step = 0, and post-step rises by 1.0 for unit step
        gyro_seg = np.asarray(y_seg, dtype=float)
        gyro_norm = (gyro_seg - y0) / step_amp
        gyro_norm = np.nan_to_num(gyro_norm, nan=0.0, posinf=0.0, neginf=0.0)

        # Normalize fitted curve using the SAME baseline and amplitude
        if y_fit is not None:
            y_fit = np.asarray(y_fit, dtype=float)
            y_fit_norm = (y_fit - y0) / step_amp
            y_fit_norm = np.nan_to_num(y_fit_norm, nan=0.0, posinf=0.0, neginf=0.0)
        else:
            y_fit_norm = None

        # Align time display to start at zero
        t_display = t_seg - t_seg[0] if len(t_seg) > 0 else t_seg

        # Ensure t_display and t_fit are numeric and finite
        t_display = np.asarray(t_display, dtype=float)
        if t_fit is not None:
            try:
                t_fit = np.asarray(t_fit, dtype=float)
            except Exception:
                t_fit = None

        # Clean plotted arrays
        gyro_norm = np.nan_to_num(gyro_norm, nan=0.0, posinf=0.0, neginf=0.0)
        if y_fit_norm is not None:
            y_fit_norm = np.nan_to_num(y_fit_norm, nan=0.0, posinf=0.0, neginf=0.0)

        # Safe plotting helpers to avoid adding traces with NaNs or mismatched lengths
        def _is_finite_array(a):
            try:
                a = np.asarray(a, dtype=float)
                return a.size > 0 and np.all(np.isfinite(a))
            except Exception:
                return False

        def _safe_plot(x, y, **kwargs):
            try:
                if x is None or y is None:
                    return None
                xa = np.asarray(x, dtype=float)
                ya = np.asarray(y, dtype=float)
                if xa.size == 0 or ya.size == 0 or xa.size != ya.size:
                    return None
                if not (np.all(np.isfinite(xa)) and np.all(np.isfinite(ya))):
                    return None
                return self.plot_widget.plot(xa, ya, **kwargs)
            except Exception:
                return None

        # RC is shown as reference baseline at 0; gyro and fitted are centered so pre-step == 0
        # RC Command line removed per user request
        _safe_plot(t_display, gyro_norm, pen=self.PLOT_COLORS['gyro'], name='Gyro Response')
        if t_fit is not None and y_fit_norm is not None:
            _safe_plot(t_fit, y_fit_norm, pen=pg.mkPen('#66BB6A', width=2, style=pg.QtCore.Qt.PenStyle.DotLine), name='Fitted Model')

        # Add horizontal reference line at Y=1.0 (expected post-step value for unit step)
        reference_line = pg.InfiniteLine(pos=1.0, angle=0, pen=pg.mkPen('white', width=2, style=pg.QtCore.Qt.PenStyle.DashLine))
        self.plot_widget.addItem(reference_line)

        # adjust Y range to center around 0 and include both traces comfortably
        ymin, ymax = -1.0, 1.0
        try:
            y_vals = []
            if gyro_norm is not None and len(gyro_norm) > 0:
                y_vals.append(np.nanmin(gyro_norm))
                y_vals.append(np.nanmax(gyro_norm))
            if y_fit_norm is not None and len(y_fit_norm) > 0:
                y_vals.append(np.nanmin(y_fit_norm))
                y_vals.append(np.nanmax(y_fit_norm))
            if y_vals:
                ymin = float(min(y_vals))
                ymax = float(max(y_vals))
                span = max(ymax - ymin, 1e-3)
                margin = span * 0.2
                self.plot_widget.setYRange(ymin - margin, ymax + margin)
        except Exception:
            pass

        # Display metrics from analyzer (more reliable than simple heuristics)
        pretty = []
        for k, v in metrics.items():
            if isinstance(v, float):
                pretty.append(f"{k}: {v:.4g}")
            else:
                pretty.append(f"{k}: {v}")

        # Calculate overshoot from normalized gyro response if available
        if gyro_norm is not None and len(gyro_norm) > 0:
            peak_val = np.nanmax(gyro_norm)
            # For a unit step, final value should be around 1.0, overshoot = (peak - 1.0) * 100
            overshoot_pct = (peak_val - 1.0) * 100.0
            pretty.append(f"Peak Value (normalized): {peak_val:.4f}")
            pretty.append(f"Overshoot: {overshoot_pct:.2f}%")

        self.metrics_text.setText('\n'.join(pretty))
        # add markers: delay, peak, rise, settling (when available)
        try:
            td = metrics.get('time_delay_s', None)
            peak_t = metrics.get('peak_time_s', None)
            rt = metrics.get('rise_time_s', None)
            st = metrics.get('settling_time_s', None)
            # vertical markers
            if td is not None and np.isfinite(td):
                # only add if within a reasonable x-range
                try:
                    x_min = float(np.nanmin(t_display))
                    x_max = float(np.nanmax(t_display))
                    if td >= x_min - 1e6 and td <= x_max + 1e6:
                        v = pg.InfiniteLine(pos=float(td), angle=90, pen=pg.mkPen('gray', style=pg.QtCore.Qt.PenStyle.DashLine))
                        self.plot_widget.addItem(v)
                except Exception:
                    pass
            if peak_t is not None and np.isfinite(peak_t):
                try:
                    x_min = float(np.nanmin(t_display))
                    x_max = float(np.nanmax(t_display))
                    if peak_t >= x_min - 1e6 and peak_t <= x_max + 1e6:
                        v2 = pg.InfiniteLine(pos=float(peak_t), angle=90, pen=pg.mkPen('red'))
                        self.plot_widget.addItem(v2)
                except Exception:
                    pass

            # text annotations — place them separated and slightly larger
            try:
                x_max = float(np.nanmax(t_display)) if np.any(np.isfinite(t_display)) else 0.1
            except Exception:
                x_max = 0.1
            x_base = x_max * 0.02
            # compute y positions in data coordinates using current y-range
            try:
                view_range = self.plot_widget.viewRange()
                y_min_plot, y_max_plot = view_range[1][0], view_range[1][1]
            except Exception:
                y_min_plot, y_max_plot = ymin, ymax
            # Rise and Settle tags removed per user request
            pass
        except Exception:
            pass
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

        window_step_index = step_index - start

        time_window = time[start:end]
        # raw_time_us will always be microseconds for compatibility with analyzer
        if time_col_name == 'loopIteration':
            # convert iterations to microseconds
            time_s = time_window * (1 / self.loop_freq)
            raw_time_us = (time_s * 1_000_000).astype(int)
        elif time_col_name == 'time (us)':
            time_s = time_window / 1_000_000
            raw_time_us = time_window.astype(int)
        else:
            # try best-effort: assume time is in microseconds if large, else seconds
            if np.max(time_window) > 1e6:
                raw_time_us = time_window.astype(int)
                time_s = time_window / 1_000_000
            else:
                time_s = time_window
                raw_time_us = (time_s * 1_000_000).astype(int)

        time_aligned = time_s - time_s[window_step_index]

        return time_aligned, rc[start:end], gyro[start:end], window_step_index, raw_time_us

    def _normalize_signals(self, rc, gyro, step_index):
        if step_index < 10 or len(rc) - step_index < 20:
            return None, None, "Not enough data around step"

        pre_step_rc = np.mean(rc[:step_index-5])
        post_step_rc = np.mean(rc[step_index+10:])
        step_height = post_step_rc - pre_step_rc

        if np.isclose(step_height, 0):
            return None, None, "Step height is zero"

        rc_norm = (rc - pre_step_rc) / step_height

        pre_step_gyro = np.mean(gyro[:step_index-5])
        gyro_norm = (gyro - pre_step_gyro) / step_height

        return rc_norm, gyro_norm, None
