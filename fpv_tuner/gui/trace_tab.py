import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg

class TraceTab(QWidget):
    PLOT_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    def __init__(self):
        super().__init__()
        self.logs = {}

        layout = QVBoxLayout(self)
        self.plot_widget = pg.PlotWidget(title="Raw Gyro and RC Command")
        self.plot_widget.addLegend()
        self.plot_widget.setDownsampling(auto=True, mode='peak')
        self.plot_widget.setClipToView(True)
        layout.addWidget(self.plot_widget)

    def set_data(self, logs):
        self.logs = logs
        self.update_plots()

    def update_plots(self):
        self.plot_widget.clear()
        if not self.logs:
            return

        self.plot_widget.setLabel('bottom', 'Time (s)')

        for i, (filename, log_data) in enumerate(self.logs.items()):
            color = self.PLOT_COLORS[i % len(self.PLOT_COLORS)]
            short_name = os.path.basename(filename)

            time_col = self._find_column(log_data, ['time (us)', 'time'])
            if not time_col:
                continue

            time_s = log_data[time_col] / 1_000_000

            # Plot Gyro data
            self._plot_axis_data(log_data, time_s, 'gyroADC', color, short_name)
            # Plot RC Command data (optional, can be noisy)
            # self._plot_axis_data(log_data, time_s, 'rcCommand', color, short_name)

    def _plot_axis_data(self, df, time_s, prefix, color, log_name):
        # Let's just plot Roll and Pitch for clarity
        for i in range(2): # 0 for Roll, 1 for Pitch
            col_name = self._find_column(df, [f'{prefix}[{i}]'])
            if col_name:
                # Use a slightly different style for the second axis if needed
                pen = pg.mkPen(color=color, style=pg.QtCore.Qt.PenStyle.SolidLine if i == 0 else pg.QtCore.Qt.PenStyle.DotLine)
                self.plot_widget.plot(time_s, df[col_name], pen=pen, name=f"{log_name} - {col_name}")

    def _find_column(self, df, possible_names):
        for name in possible_names:
            if name in df.columns:
                return name
        return None
