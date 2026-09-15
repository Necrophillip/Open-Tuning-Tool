with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

target = """    def _render_heatmap(self):
        analysis = self.state.analysis
        heatmaps = analysis.heatmaps if analysis else {}"""

replacement = """    def _render_heatmap(self):
        analysis = self.state.analysis
        if not analysis:
            heatmaps = {}
        elif self.signal_combo.currentIndex() == 1:
            heatmaps = getattr(analysis, "dterm_heatmaps", {})
        else:
            heatmaps = getattr(analysis, "heatmaps", {})"""

code = code.replace(target, replacement)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
