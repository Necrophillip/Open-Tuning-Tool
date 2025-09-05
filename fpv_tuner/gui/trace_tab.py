import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg

class TraceTab(QWidget):
    PLOT_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
    AXES_MAPPING = {
        'Roll':  {'rc': 'rcCommand[0]', 'gyro': 'gyroADC[0]', 'dterm': ['dTerm[0]', 'axisD[0]']},
        'Pitch': {'rc': 'rcCommand[1]', 'gyro': 'gyroADC[1]', 'dterm': ['dTerm[1]', 'axisD[1]']},
        'Yaw':   {'rc': 'rcCommand[2]', 'gyro': 'gyroADC[2]', 'dterm': ['dTerm[2]', 'axisD[2]']},
    }

    def __init__(self):
        super().__init__()
        self.logs = {}

        layout = QVBoxLayout(self)
        # Use GraphicsLayoutWidget for multiple subplots
        self.win = pg.GraphicsLayoutWidget(title="Trace Viewer")
        layout.addWidget(self.win)

        # Create 3 plot items
        self.plots = []
        for i, axis_name in enumerate(self.AXES_MAPPING.keys()):
            p = self.win.addPlot(row=i, col=0)
            p.setLabel('left', axis_name)
            p.addLegend()
            self.plots.append(p)
            # Link X axes
            if i > 0:
                p.setXLink(self.plots[0])

        self.plots[-1].setLabel('bottom', 'Time (s)')


    def set_data(self, logs):
        self.logs = logs
        self.update_plots()

    def update_plots(self):
        # Clear all plots first
        for p in self.plots:
            p.clear()

        if not self.logs:
            return

        for i, (filename, log_data) in enumerate(self.logs.items()):
            color = self.PLOT_COLORS[i % len(self.PLOT_COLORS)]
            short_name = os.path.basename(filename)

            time_col = self._find_column(log_data, ['time (us)', 'time'])
            if not time_col:
                continue

            time_s = log_data[time_col] / 1_000_000

            # Iterate through each axis and its corresponding plot
            for plot_idx, (axis_name, cols) in enumerate(self.AXES_MAPPING.items()):
                current_plot = self.plots[plot_idx]

                # Get columns for this axis
                rc_col = self._find_column(log_data, [cols['rc']])
                gyro_col = self._find_column(log_data, [cols['gyro']])
                dterm_col = self._find_column(log_data, cols['dterm'])

                # Plot data
                if rc_col:
                    current_plot.plot(time_s, log_data[rc_col], pen=pg.mkPen(color, style=pg.QtCore.Qt.PenStyle.SolidLine), name=f"{short_name} - RC Command")
                if gyro_col:
                    current_plot.plot(time_s, log_data[gyro_col], pen=pg.mkPen(color, style=pg.QtCore.Qt.PenStyle.DashLine), name=f"{short_name} - Gyro")
                if dterm_col:
                    current_plot.plot(time_s, log_data[dterm_col], pen=pg.mkPen(color, style=pg.QtCore.Qt.PenStyle.DotLine), name=f"{short_name} - D-Term")

    def _find_column(self, df, possible_names):
        for name in possible_names:
            if name in df.columns:
                return name
        return None
