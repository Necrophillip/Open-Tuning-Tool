import re

with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    content = f.read()

# Define the new build UI and render code
new_build_and_render = """    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        layout.setSpacing(Spacing.SM)

        layout.addWidget(self._make_title("Export & Apply"))
        layout.addWidget(self._make_subtitle(
            "Review the analysis, then apply the recommended changes to your quad."
        ))

        # ── Step response (3 axes) ─────────────────────────────────
        layout.addWidget(_section_label("📈  Step Response"))
        step_row = QHBoxLayout()
        step_row.setSpacing(Spacing.SM)
        self._step_plots = {}
        for axis in ("roll", "pitch", "yaw"):
            plot = pg.PlotWidget()
            plot.setTitle(axis.capitalize())
            plot.setLabel("bottom", "Time (s)")
            plot.setLabel("left", "Normalized")
            plot.showGrid(x=True, y=True, alpha=0.2)
            plot.setDownsampling(auto=True, mode="peak")
            self._step_plots[axis] = plot
            step_row.addWidget(plot)
        layout.addLayout(step_row, 2)

        # ── Gyro Noise Heatmap ─────────────────────────────────────
        layout.addWidget(_section_label("🔥 Gyro Noise Heatmap"))
        gyro_row = QHBoxLayout()
        gyro_row.setSpacing(Spacing.SM)
        self._gyro_views = {}
        for axis in ("roll", "pitch", "yaw"):
            plot_item = pg.PlotItem(title="")
            plot_item.setLabel("bottom", "Throttle (%)")
            plot_item.setLabel("left", "Frequency (Hz)")
            view = pg.ImageView(view=plot_item)
            view.setColorMap(_make_thermal_colormap())
            view.ui.histogram.hide()
            view.ui.roiBtn.hide()
            view.ui.menuBtn.hide()
            view.setMinimumHeight(200)
            view.getView().invertY(False)
            self._gyro_views[axis] = view
            gyro_row.addWidget(view)
        layout.addLayout(gyro_row, 2)

        # ── D-Term Noise Heatmap ───────────────────────────────────
        layout.addWidget(_section_label("🔥 D-Term Noise Heatmap"))
        dterm_row = QHBoxLayout()
        dterm_row.setSpacing(Spacing.SM)
        self._dterm_views = {}
        for axis in ("roll", "pitch", "yaw"):
            plot_item = pg.PlotItem(title="")
            plot_item.setLabel("bottom", "Throttle (%)")
            plot_item.setLabel("left", "Frequency (Hz)")
            view = pg.ImageView(view=plot_item)
            view.setColorMap(_make_thermal_colormap())
            view.ui.histogram.hide()
            view.ui.roiBtn.hide()
            view.ui.menuBtn.hide()
            view.setMinimumHeight(200)
            view.getView().invertY(False)
            self._dterm_views[axis] = view
            dterm_row.addWidget(view)
        layout.addLayout(dterm_row, 2)

        # ── RPM Filter Harmonics ───────────────────────────────────
        layout.addWidget(_section_label("🎵 RPM Filter Harmonics"))
        harm_row = QHBoxLayout()
        harm_row.setSpacing(Spacing.SM)
        self._harm_plots = {}
        for axis in ("roll", "pitch", "yaw"):
            plot = pg.PlotWidget()
            plot.setTitle(axis.capitalize())
            plot.setLabel("bottom", "Throttle (%)")
            plot.setLabel("left", "Frequency (Hz)")
            plot.showGrid(x=True, y=True, alpha=0.2)
            plot.setMinimumHeight(200)
            self._harm_plots[axis] = plot
            harm_row.addWidget(plot)
        layout.addLayout(harm_row, 2)

        # ── Changes summary (compact) ──────────────────────────────
        self.changes_label = QLabel("No changes recommended yet.")
        self.changes_label.setTextFormat(Qt.TextFormat.RichText)
        self.changes_label.setWordWrap(True)
        self.changes_label.setMaximumHeight(90)
        self.changes_label.setStyleSheet(f\"\"\"
            background-color: {Colors.BG_SURFACE};
            border: 1px solid {Colors.BORDER_SUBTLE};
            border-radius: {Radius.MD}px;
            padding: {Spacing.SM}px;
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SIZE_CAPTION}px;
        \"\"\")
        layout.addWidget(self.changes_label)

        # ── Action buttons ─────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(Spacing.MD)

        self.write_btn = QPushButton("✅  Apply to FC")
        self.write_btn.setProperty("variant", "primary")
        self.write_btn.setToolTip(
            "Connect the FC via USB and apply these CLI changes directly."
        )
        self.write_btn.clicked.connect(self._write_to_fc)
        btn_layout.addWidget(self.write_btn)

        self.show_cli_btn = QPushButton("🖥  Show CLI")
        self.show_cli_btn.setProperty("variant", "ghost")
        self.show_cli_btn.clicked.connect(self._show_cli_popup)
        btn_layout.addWidget(self.show_cli_btn)

        self.copy_btn = QPushButton("📋  Copy to Clipboard")
        self.copy_btn.setProperty("variant", "ghost")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        btn_layout.addWidget(self.copy_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def on_enter(self):
        self._generate_recommendations()
        self._render_review()

    def can_proceed(self) -> bool:
        return True

    def _render_review(self):
        analysis = self.state.analysis
        if not analysis:
            return
            
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
            
        gyro_heatmaps = getattr(analysis, "heatmaps", {})
        dterm_heatmaps = getattr(analysis, "dterm_heatmaps", {})
        
        self._update_heatmaps(self._gyro_views, gyro_heatmaps)
        self._update_heatmaps(self._dterm_views, dterm_heatmaps)
        self._render_harmonics(self._harm_plots, gyro_heatmaps)

    def _update_heatmaps(self, views, heatmaps):
        for axis, view in views.items():
            view.getView().clear()
            data = heatmaps.get(axis)
            if not data:
                view.getView().setTitle(f"{axis.capitalize()} (No data)")
                view.clear()
                continue
                
            view.getView().setTitle("")
            hm = data["heatmap"]
            img = hm.T
            freq_max = data["freq"][-1]
            
            tr = pg.QtGui.QTransform()
            tr.scale(100.0 / img.shape[0], freq_max / img.shape[1])
            
            v_min, v_max = np.nanmin(img), np.nanpercentile(img, 99.5)
            if np.isnan(v_max) or v_min == v_max: v_max = v_min + 1
            
            view.setImage(img, autoRange=False, levels=(v_min, v_max), transform=tr)
            
            mean_val = np.nanmean(img)
            peak_val = np.nanmax(img)
            
            axis_label = pg.TextItem(axis, color=(255, 255, 255), anchor=(0, 0))
            axis_label.setPos(2, freq_max - (freq_max * 0.05))
            view.getView().addItem(axis_label)
            
            stats_label = pg.TextItem(f"mean={mean_val:.3f}\\npeak={peak_val:.3f}", color=(255, 255, 255), anchor=(1, 0))
            stats_label.setPos(98, freq_max - (freq_max * 0.05))
            view.getView().addItem(stats_label)
            
            view.getView().setLimits(xMin=0, xMax=100, yMin=0, yMax=freq_max)
            view.getView().setXRange(0, 100, padding=0)
            view.getView().setYRange(0, freq_max, padding=0)
            
            x_ax = view.getView().getAxis("bottom")
            x_ax.setTicks([[(i, str(i)) for i in range(0, 101, 20)]])
            y_ax = view.getView().getAxis("left")
            y_ax.setTicks([[(i, str(i)) for i in range(0, int(freq_max) + 1, 200)]])

    def _render_harmonics(self, plots, heatmaps):
        for axis, plot in plots.items():
            plot.clear()
            data = heatmaps.get(axis)
            if not data or "h1" not in data:
                plot.setTitle(f"{axis.capitalize()} (No data)")
                continue
                
            plot.setTitle(f"{axis.capitalize()}")
            tc = data["throttle"]
            colors = ["#00ffff", "#ffaa00", "#ffff00"]
            names = ["H1 (Fundamental)", "H2 (2x)", "H3 (3x)"]
            
            for i, h_key in enumerate(["h1", "h2", "h3"]):
                if h_key in data:
                    plot.plot(tc, data[h_key], name=names[i], pen=pg.mkPen(colors[i], width=2))
                    
            freq_max = data["freq"][-1]
            plot.setLimits(xMin=0, xMax=100, yMin=0, yMax=freq_max)
            plot.setXRange(0, 100, padding=0)
            plot.setYRange(0, freq_max, padding=0)

    # ── Recommendation generation ─────────────────────────────────"""

# Extract up to _build_ui
start_idx = content.find("    def _build_ui(self):")
end_idx = content.find("    # ── Recommendation generation ─────────────────────────────────")

new_content = content[:start_idx] + new_build_and_render + content[end_idx + 68:]

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(new_content)
