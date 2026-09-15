with open("fpv_tuner/ui/pages/analysis_page.py", "r") as f:
    code = f.read()

target = """            results["heatmaps"] = self._analyze_heatmaps(df)
            job.report_progress(85, "Evaluating PID steps...")"""

replacement = """            results["heatmaps"] = self._analyze_heatmaps(df, col_prefix="gyroADC")
            results["dterm_heatmaps"] = self._analyze_heatmaps(df, col_prefix="axisD")
            job.report_progress(85, "Evaluating PID steps...")"""

code = code.replace(target, replacement)
with open("fpv_tuner/ui/pages/analysis_page.py", "w") as f:
    f.write(code)
