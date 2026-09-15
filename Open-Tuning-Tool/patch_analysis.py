with open("fpv_tuner/ui/pages/analysis_page.py", "r") as f:
    code = f.read()

target = """    def _analyze_heatmaps(self, df):
        from fpv_tuner.analysis.summary import compute_noise_heatmap
        result = {}
        for axis in ("roll", "pitch", "yaw"):
            heatmap = compute_noise_heatmap(df, axis)
            if heatmap is not None:
                result[axis] = heatmap
        return result"""

replacement = """    def _analyze_heatmaps(self, df, col_prefix="gyroADC"):
        from fpv_tuner.analysis.summary import compute_noise_heatmap
        result = {}
        for axis in ("roll", "pitch", "yaw"):
            heatmap = compute_noise_heatmap(df, axis, col_prefix=col_prefix)
            if heatmap is not None:
                result[axis] = heatmap
        return result"""

code = code.replace(target, replacement)
with open("fpv_tuner/ui/pages/analysis_page.py", "w") as f:
    f.write(code)
