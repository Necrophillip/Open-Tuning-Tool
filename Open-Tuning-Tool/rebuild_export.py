with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

import re

# 1. Replace the heatmap section in _build_ui
target_build_ui = r'''        # ── Noise heatmap ──────────────────────────────────────────
        layout\.addWidget\(_section_label\("🔥  Noise Heatmap"\)\)
        heat_controls = QHBoxLayout\(\)
        heat_controls\.addWidget\(QLabel\("Axis:"\)\)
        self\._heatmap_axis_combo = QComboBox\(\)
        self\._heatmap_axis_combo\.addItems\(\["roll", "pitch", "yaw"\]\)
        self\._heatmap_axis_combo\.currentTextChanged\.connect\(self\._render_heatmap\)
        heat_controls\.addWidget\(self\._heatmap_axis_combo\)
        heat_controls\.addStretch\(\)
        layout\.addLayout\(heat_controls\)

        heatmap_plot_item = pg\.PlotItem\(\)
        heatmap_plot_item\.setLabel\("bottom", "Throttle \(%\)"\)
        heatmap_plot_item\.setLabel\("left", "Frequency \(Hz\)"\)
        self\._heatmap_view = pg\.ImageView\(view=heatmap_plot_item\)
        self\._heatmap_view\.setColorMap\(_make_thermal_colormap\(\)\)
        layout\.addWidget\(self\._heatmap_view, 2\)'''

replacement_build_ui = """        # ── Noise heatmap ──────────────────────────────────────────
        heat_header = QHBoxLayout()
        heat_header.addWidget(_section_label("🔥  Noise Heatmap"))
        heat_header.addStretch()
        self.signal_combo = QComboBox()
        self.signal_combo.addItems([
            "Gyro (Puro)",
            "Gyro + Armónicos",
            "D-Term (Puro)",
            "D-Term + Armónicos"
        ])
        self.signal_combo.currentIndexChanged.connect(self._render_review)
        self.signal_combo.setStyleSheet(f\"\"\"
            QComboBox {{
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_SUBTLE};
                padding: 4px 10px;
                border-radius: 4px;
            }}
        \"\"\")
        heat_header.addWidget(self.signal_combo)
        layout.addLayout(heat_header)
        
        self.heat_row = QHBoxLayout()
        self.heat_row.setSpacing(Spacing.SM)
        layout.addLayout(self.heat_row)"""

code = re.sub(target_build_ui, replacement_build_ui, code, flags=re.DOTALL)


# 2. Replace _render_review and _render_heatmap
target_renders = r'''    def _render_review\(self\):
.*?    # ── Recommendation generation ─────────────────────────────────'''

replacement_renders = """    def _render_review(self):
        analysis = self.state.analysis
        step_responses = analysis.step_responses if analysis else {}
        for axis, plot in self._step_plots.items():
            plot.clear()
            data = step_responses.get(axis)
            if not data:
                plot.setTitle(f"{axis.capitalize()} (no data)")
                continue
            plot.plot(data["t"], data["response"], pen=pg.mkPen("#42A5F5", width=2))
            plot.addItem(pg.InfiniteLine(pos=1.0, angle=0, pen=pg.mkPen("white", width=1,
                         style=Qt.PenStyle.DashLine)))
            title = axis.capitalize()
            if data.get("overshoot_pct") is not None:
                title += f"  ·  {data['overshoot_pct']:.0f}% overshoot"
            plot.setTitle(title)
        self._render_heatmap()

    def _render_heatmap(self):
        analysis = self.state.analysis
        idx = self.signal_combo.currentIndex()
        if not analysis:
            heatmaps = {}
        elif idx in (2, 3):
            heatmaps = getattr(analysis, "dterm_heatmaps", {})
        else:
            heatmaps = getattr(analysis, "heatmaps", {})
            
        # Limpiar
        while self.heat_row.count():
            item = self.heat_row.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        from pyqtgraph import PlotCurveItem
        from PyQt6.QtCore import Qt
        
        for axis in ["roll", "pitch", "yaw"]:
            plot_item = pg.PlotItem(title=axis.capitalize())
            plot_item.setLabel("bottom", "Throttle (%)")
            plot_item.setLabel("left", "Frequency (Hz)")

            view = pg.ImageView(view=plot_item)
            view.setColorMap(_make_thermal_colormap())
            view.ui.histogram.hide()
            view.ui.roiBtn.hide()
            view.ui.menuBtn.hide()
            view.setMinimumHeight(200)
            
            self.heat_row.addWidget(view)
            
            data = heatmaps.get(axis)
            if data is None:
                continue
                
            hm = data["heatmap"]
            img = hm.T
            freq_max = data["freq"][-1]
            
            tr = pg.QtGui.QTransform()
            tr.scale(100.0 / img.shape[0], freq_max / img.shape[1])
            
            view.setImage(img, autoRange=False, transform=tr)
            
            view.getView().setLimits(xMin=0, xMax=100, yMin=0, yMax=freq_max)
            view.getView().setXRange(0, 100, padding=0)
            view.getView().setYRange(0, freq_max, padding=0)
            
            x_ax = view.getView().getAxis("bottom")
            x_ax.setTicks([[(i, str(i)) for i in range(0, 101, 20)]])
            y_ax = view.getView().getAxis("left")
            y_ax.setTicks([[(i, str(i)) for i in range(0, int(freq_max) + 1, 200)]])
            
            if idx in (1, 3) and "h1" in data:
                tc = data["throttle"]
                colors = ["#00ffff", "#ffaa00", "#ffff00"]
                for i, h_key in enumerate(["h1", "h2", "h3"]):
                    if h_key in data:
                        curve = PlotCurveItem(
                            tc, data[h_key],
                            pen=pg.mkPen(colors[i], width=2, style=Qt.PenStyle.DashLine)
                        )
                        curve.setZValue(10)
                        view.getView().addItem(curve)

    # ── Recommendation generation ─────────────────────────────────"""

code = re.sub(target_renders, replacement_renders, code, flags=re.DOTALL)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
