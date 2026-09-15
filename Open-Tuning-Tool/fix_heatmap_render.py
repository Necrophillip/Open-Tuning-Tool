with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

target = """    def _render_heatmap(self):
        analysis = self.state.analysis
        if not analysis:
            heatmaps = {}
        elif self.signal_combo.currentIndex() == 1:
            heatmaps = getattr(analysis, "dterm_heatmaps", {})
        else:
            heatmaps = getattr(analysis, "heatmaps", {})"""

replacement = """    def _render_heatmap(self):
        analysis = self.state.analysis
        idx = self.signal_combo.currentIndex()
        if not analysis:
            heatmaps = {}
        elif idx in (2, 3):
            heatmaps = getattr(analysis, "dterm_heatmaps", {})
        else:
            heatmaps = getattr(analysis, "heatmaps", {})"""

code = code.replace(target, replacement)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
