import re

with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

target = """            y_ax = view.getView().getAxis("left")
            y_ax.setTicks([[(i, str(i)) for i in range(0, int(freq_max) + 1, 200)]])"""

replacement = """            y_ax = view.getView().getAxis("left")
            y_ax.setTicks([[(i, str(i)) for i in range(0, int(freq_max) + 1, 200)]])
            
            # Remove old curves
            from pyqtgraph import PlotCurveItem
            from PyQt6.QtCore import Qt
            for item in list(view.getView().addedItems):
                if isinstance(item, PlotCurveItem):
                    view.getView().removeItem(item)
                    
            # Add harmonic overlays
            if "h1" in data:
                tc = data["throttle"]
                colors = ["#00ffff", "#ffaa00", "#ffff00"] # Cyan, Orange, Yellow
                for i, h_key in enumerate(["h1", "h2", "h3"]):
                    if h_key in data:
                        curve = PlotCurveItem(
                            tc, data[h_key],
                            pen=pg.mkPen(colors[i], width=2, style=Qt.PenStyle.DashLine)
                        )
                        view.getView().addItem(curve)"""

code = code.replace(target, replacement)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
