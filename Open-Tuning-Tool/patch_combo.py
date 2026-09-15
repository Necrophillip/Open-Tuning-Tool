with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

# Fix 1: The combo box items
target_combo = """        self.signal_combo = QComboBox()
        self.signal_combo.addItems(["Gyro", "D-Term"])
        self.signal_combo.currentIndexChanged.connect(self._render_review)"""

replacement_combo = """        self.signal_combo = QComboBox()
        self.signal_combo.addItems([
            "Gyro (Puro)",
            "Gyro + Armónicos",
            "D-Term (Puro)",
            "D-Term + Armónicos"
        ])
        self.signal_combo.currentIndexChanged.connect(self._render_review)"""

code = code.replace(target_combo, replacement_combo)

# Fix 2: The render heatmap logic
target_render = """    def _render_heatmap(self):
        analysis = self.state.analysis
        if not analysis:
            heatmaps = {}
        elif self.signal_combo.currentIndex() == 1:
            heatmaps = getattr(analysis, "dterm_heatmaps", {})
        else:
            heatmaps = getattr(analysis, "heatmaps", {})

        for axis, view in self._heat_plots.items():"""

replacement_render = """    def _render_heatmap(self):
        analysis = self.state.analysis
        idx = self.signal_combo.currentIndex()
        
        if not analysis:
            heatmaps = {}
        elif idx in (2, 3):
            heatmaps = getattr(analysis, "dterm_heatmaps", {})
        else:
            heatmaps = getattr(analysis, "heatmaps", {})

        for axis, view in self._heat_plots.items():"""

code = code.replace(target_render, replacement_render)

# Fix 3: The harmonic drawing condition
target_harmonics = """            # Add harmonic overlays
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

replacement_harmonics = """            # Add harmonic overlays (only if selected)
            if idx in (1, 3) and "h1" in data:
                tc = data["throttle"]
                colors = ["#00ffff", "#ffaa00", "#ffff00"] # Cyan, Orange, Yellow
                for i, h_key in enumerate(["h1", "h2", "h3"]):
                    if h_key in data:
                        curve = PlotCurveItem(
                            tc, data[h_key],
                            pen=pg.mkPen(colors[i], width=2, style=Qt.PenStyle.DashLine)
                        )
                        view.getView().addItem(curve)"""

code = code.replace(target_harmonics, replacement_harmonics)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
