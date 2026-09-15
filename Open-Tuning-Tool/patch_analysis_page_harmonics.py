import re

with open("fpv_tuner/ui/pages/analysis_page.py", "r") as f:
    code = f.read()

target = """    def _analyze_heatmaps(self, df, col_prefix="gyroADC"):
        from fpv_tuner.analysis.summary import compute_noise_heatmap
        result = {}
        for axis in ("roll", "pitch", "yaw"):
            heatmap = compute_noise_heatmap(df, axis, col_prefix=col_prefix)"""

replacement = """    def _analyze_heatmaps(self, df, col_prefix="gyroADC"):
        from fpv_tuner.analysis.summary import compute_noise_heatmap
        
        motor_poles = 14
        if self.state.has_cli and self.state.cli.settings:
            try:
                motor_poles = int(self.state.cli.settings.get("motor_poles", 14))
            except ValueError:
                pass
                
        result = {}
        for axis in ("roll", "pitch", "yaw"):
            heatmap = compute_noise_heatmap(df, axis, col_prefix=col_prefix, motor_poles=motor_poles)"""

code = code.replace(target, replacement)

with open("fpv_tuner/ui/pages/analysis_page.py", "w") as f:
    f.write(code)
