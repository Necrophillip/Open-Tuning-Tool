with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

import re

# Add dropdown to the Noise Heatmap section label row
target_section = """        # ── Noise heatmap (3 axes) ─────────────────────────────────
        layout.addWidget(_section_label("🔥  Noise Heatmap"))
        heat_row = QHBoxLayout()
        heat_row.setSpacing(Spacing.SM)
        self._heat_plots = {}"""

replacement_section = """        # ── Noise heatmap (3 axes) ─────────────────────────────────
        heat_header = QHBoxLayout()
        heat_header.addWidget(_section_label("🔥  Noise Heatmap"))
        heat_header.addStretch()
        self.signal_combo = QComboBox()
        self.signal_combo.addItems(["Gyro", "D-Term"])
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
        
        heat_row = QHBoxLayout()
        heat_row.setSpacing(Spacing.SM)
        self._heat_plots = {}"""

code = code.replace(target_section, replacement_section)

# Update _render_review to render the selected signal
target_render = """        heatmaps = analysis.heatmaps if analysis else {}
        for axis, view in self._heat_plots.items():
            view.clear()
            data = heatmaps.get(axis)
            if not data or "heatmap" not in data:
                continue"""

replacement_render = """        signal_idx = self.signal_combo.currentIndex()
        if signal_idx == 1:
            heatmaps = analysis.dterm_heatmaps if analysis else {}
        else:
            heatmaps = analysis.heatmaps if analysis else {}

        for axis, view in self._heat_plots.items():
            view.clear()
            data = heatmaps.get(axis)
            if not data or "heatmap" not in data:
                continue"""

code = code.replace(target_render, replacement_render)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
