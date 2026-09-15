with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

import re

target1 = r'''        heat_row = QHBoxLayout\(\)
        heat_row\.setSpacing\(Spacing\.SM\)
        self\._heat_plots = \{\}

        for axis in \["roll", "pitch", "yaw"\]:
            plot_item = pg\.PlotItem\(title=axis\.capitalize\(\)\)
            plot_item\.setLabel\("bottom", "Throttle \(%\)"\)
            plot_item\.setLabel\("left", "Frequency \(Hz\)"\)

            view = pg\.ImageView\(view=plot_item\)
            view\.setColorMap\(_make_thermal_colormap\(\)\)
            view\.ui\.histogram\.hide\(\)
            view\.ui\.roiBtn\.hide\(\)
            view\.ui\.menuBtn\.hide\(\)
            view\.setMinimumHeight\(200\)

            self\._heat_plots\[axis\] = view
            heat_row\.addWidget\(view\)
        
        layout\.addLayout\(heat_row\)'''

replacement1 = """        self.heat_row = QHBoxLayout()
        self.heat_row.setSpacing(Spacing.SM)
        layout.addLayout(self.heat_row)
        # Graphics will be created dynamically in _render_heatmap"""

code = re.sub(target1, replacement1, code)


target2 = r'''    def _render_heatmap\(self\):
.*?            # Add harmonic overlays \(only if selected\)
            if idx in \(1, 3\) and "h1" in data:
                tc = data\["throttle"\]
                colors = \["#00ffff", "#ffaa00", "#ffff00"\] # Cyan, Orange, Yellow
                for i, h_key in enumerate\(\\["h1", "h2", "h3"\\]\):
                    if h_key in data:
                        curve = PlotCurveItem\(
                            tc, data\[h_key\],
                            pen=pg\.mkPen\(colors\[i\], width=2, style=Qt\.PenStyle\.DashLine\)
                        \)
                        view\.getView\(\)\.addItem\(curve\)'''

replacement2 = """    def _render_heatmap(self):
        analysis = self.state.analysis
        idx = self.signal_combo.currentIndex()
        if not analysis:
            heatmaps = {}
        elif idx in (2, 3):
            heatmaps = getattr(analysis, "dterm_heatmaps", {})
        else:
            heatmaps = getattr(analysis, "heatmaps", {})
            
        # Destruir temporalmente los graficos anteriores
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
                        view.getView().addItem(curve)"""

code = re.sub(target2, replacement2, code, flags=re.DOTALL)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
