import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel,
    QDoubleSpinBox, QFormLayout, QTextEdit
)
import pyqtgraph as pg
import numpy as np
from fpv_tuner.analysis.system_identification import (
    analyze_axis_response, first_order_step_model, second_order_step_model
)

class StepResponseTab(QWidget):
    AXES_MAP = {
        "Roll":  {'rc': 'rcCommand[0]', 'gyro': 'gyroADC[0]'},
        "Pitch": {'rc': 'rcCommand[1]', 'gyro': 'gyroADC[1]'},
        "Yaw":   {'rc': 'rcCommand[2]', 'gyro': 'gyroADC[2]'},
    }
    PLOT_COLORS = {"Roll": "r", "Pitch": "g", "Yaw": "b"}

    def __init__(self):
        super().__init__()
        self.logs = {}
        self.current_log_path = None

        main_layout = QVBoxLayout(self)

        # --- Top Controls ---
        controls_container = QWidget()
        controls_layout = QHBoxLayout(controls_container)
        main_layout.addWidget(controls_container)

        # --- Content Layout (Plot + Metrics) ---
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        self.plot_widget = pg.PlotWidget(title="Averaged & Normalized Step Response")
        self.plot_widget.addLegend()
        self.plot_widget.setLabel('bottom', 'Time (ms)')
        self.plot_widget.setLabel('left', 'Normalized Response')
        self.plot_widget.showGrid(x=True, y=True)
        content_layout.addWidget(self.plot_widget, 3)

        self.metrics_text = QTextEdit()
        self.metrics_text.setReadOnly(True)
        self.metrics_text.setFontFamily("monospace")
        content_layout.addWidget(self.metrics_text, 1)

        # --- Populate Top Controls ---
        form_layout = QFormLayout()
        self.log_combo = QComboBox()
        self.threshold_spinbox = QDoubleSpinBox()
        self.threshold_spinbox.setRange(0.1, 1.0)
        self.threshold_spinbox.setValue(0.7)
        self.threshold_spinbox.setSingleStep(0.05)
        self.threshold_spinbox.setSuffix(" (Deflection %)")

        form_layout.addRow("Log File:", self.log_combo)
        form_layout.addRow("Sensitivity:", self.threshold_spinbox)
        controls_layout.addLayout(form_layout)
        controls_layout.addStretch()

        # --- Connections ---
        self.log_combo.currentTextChanged.connect(self.run_analysis)
        self.threshold_spinbox.valueChanged.connect(self.run_analysis)

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

        time_col = self._find_column(log_data, ['time (us)', 'time'])
        if not time_col:
            self.metrics_text.setText("Error: 'time (us)' column not found.")
            return

        time_data = log_data[time_col].to_numpy()
        threshold_ratio = self.threshold_spinbox.value()

        full_metrics_text = ""

        for axis_name, cols in self.AXES_MAP.items():
            rc_col = self._find_column(log_data, [cols['rc']])
            gyro_col = self._find_column(log_data, [cols['gyro']])

            if not rc_col or not gyro_col:
                continue

            rc_data = log_data[rc_col].to_numpy()
            gyro_data = log_data[gyro_col].to_numpy()

            results = analyze_axis_response(axis_name, time_data, rc_data, gyro_data, threshold_ratio)

            full_metrics_text += f"--- {axis_name} ---\n"
            if "error" in results:
                full_metrics_text += f"  {results['error']}\n\n"
                continue

            t_avg, y_avg = results["t_avg"], results["y_avg"]
            popt1, popt2 = results["popt1"], results["popt2"]
            color = self.PLOT_COLORS[axis_name]

            # Plot average response
            self.plot_widget.plot(t_avg * 1000, y_avg, pen=pg.mkPen(color, width=2), name=f"{axis_name} Response")

            # Plot fitted models and add text
            if popt1 is not None:
                y_fit1 = first_order_step_model(t_avg, *popt1)
                self.plot_widget.plot(t_avg * 1000, y_fit1, pen=pg.mkPen(color, style=pg.QtCore.Qt.PenStyle.DashLine), name=f"{axis_name} 1st Order")
                full_metrics_text += f"1st Order: G(s) = {popt1[0]:.3f} / ({popt1[1]:.3f}s + 1)\n"

            if popt2 is not None:
                y_fit2 = second_order_step_model(t_avg, *popt2)
                self.plot_widget.plot(t_avg * 1000, y_fit2, pen=pg.mkPen(color, style=pg.QtCore.Qt.PenStyle.DotLine), name=f"{axis_name} 2nd Order")
                full_metrics_text += f"2nd Order: K={popt2[0]:.2f}, wn={popt2[1]:.1f}, ζ={popt2[2]:.2f}\n"

            full_metrics_text += "\n"

        self.metrics_text.setText(full_metrics_text)

    def _find_column(self, df, possible_names):
        for name in possible_names:
            if name in df.columns:
                return name
        return None
