with open("fpv_tuner/ui/pages/analysis_page.py", "r") as f:
    code = f.read()

target = """            # Task 6: Noise heatmaps (per axis) for the review page
            job.report_progress(99, "Building noise heatmaps...")
            results["heatmaps"] = self._analyze_heatmaps(df)
            job.report_progress(100, "Analysis complete")"""

replacement = """            # Task 6: Noise heatmaps (per axis) for the review page
            job.report_progress(99, "Building noise heatmaps...")
            results["heatmaps"] = self._analyze_heatmaps(df, col_prefix="gyroADC")
            results["dterm_heatmaps"] = self._analyze_heatmaps(df, col_prefix="axisD")
            job.report_progress(100, "Analysis complete")"""

code = code.replace(target, replacement)

with open("fpv_tuner/ui/pages/analysis_page.py", "w") as f:
    f.write(code)
