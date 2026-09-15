with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

# First, modify the _build_ui where heat_row is created.
# We need to make heat_row a class attribute self.heat_row so we can rebuild it.
target_build_ui = """        heat_row = QHBoxLayout()
        heat_row.setSpacing(Spacing.SM)
        self._heat_plots = {}

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

            self._heat_plots[axis] = view
            heat_row.addWidget(view)
        
        layout.addLayout(heat_row)"""

replacement_build_ui = """        self.heat_row = QHBoxLayout()
        self.heat_row.setSpacing(Spacing.SM)
        layout.addLayout(self.heat_row)
        # Initialization deferred to _render_heatmap"""

code = code.replace(target_build_ui, replacement_build_ui)

# Second, modify _render_heatmap to destroy and recreate the widgets.
target_render = """    def _render_heatmap(self):
        analysis = self.state.analysis
        idx = self.signal_combo.currentIndex()
        if not analysis:
            heatmaps = {}
        elif idx in (2, 3):
            heatmaps = getattr(analysis, "dterm_heatmaps", {})
        else:
            heatmaps = getattr(analysis, "heatmaps", {})
        
        for axis, view in self._heat_plots.items():
            view.clear()
            data = heatmaps.get(axis)
            if data is None:
                continue
                
            hm = data["heatmap"]
            img = hm.T  # shape: (n_throttle, n_freq) -> pyqtgraph X=throttle, Y=freq
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
            
            # Remove old curves
            from pyqtgraph import PlotCurveItem
            from PyQt6.QtCore import Qt
            for item in list(view.getView().listDataItems()):
                if isinstance(item, PlotCurveItem):
                    view.getView().removeItem(item)
                    
            # Add harmonic overlays (only if selected)
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

replacement_render = """    def _render_heatmap(self):
        analysis = self.state.analysis
        idx = self.signal_combo.currentIndex()
        if not analysis:
            heatmaps = {}
        elif idx in (2, 3):
            heatmaps = getattr(analysis, "dterm_heatmaps", {})
        else:
            heatmaps = getattr(analysis, "heatmaps", {})
            
        # Destruir temporalmente los gráficos anteriores (limpieza profunda)
        while self.heat_row.count():
            item = self.heat_row.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        # Recrear los gráficos desde cero para el tipo de dato actual
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
            img = hm.T  # shape: (n_throttle, n_freq)
            freq_max = data["freq"][-1]
            
            tr = pg.QtGui.QTransform()
            tr.scale(100.0 / img.shape[0], freq_max / img.shape[1])
            
            view.setImage(img, autoRange=False, transform=tr)
            
            # Ajustar límites y ticks
            view.getView().setLimits(xMin=0, xMax=100, yMin=0, yMax=freq_max)
            view.getView().setXRange(0, 100, padding=0)
            view.getView().setYRange(0, freq_max, padding=0)
            
            x_ax = view.getView().getAxis("bottom")
            x_ax.setTicks([[(i, str(i)) for i in range(0, 101, 20)]])
            y_ax = view.getView().getAxis("left")
            y_ax.setTicks([[(i, str(i)) for i in range(0, int(freq_max) + 1, 200)]])
            
            # Add harmonic overlays (only if selected)
            if idx in (1, 3) and "h1" in data:
                tc = data["throttle"]
                colors = ["#00ffff", "#ffaa00", "#ffff00"] # Cyan, Orange, Yellow
                for i, h_key in enumerate(["h1", "h2", "h3"]):
                    if h_key in data:
                        curve = PlotCurveItem(
                            tc, data[h_key],
                            pen=pg.mkPen(colors[i], width=2, style=Qt.PenStyle.DashLine)
                        )
                        curve.setZValue(10) # Forzar que se dibuje ENCIMA del mapa de calor
                        view.getView().addItem(curve)"""

code = code.replace(target_render, replacement_render)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
