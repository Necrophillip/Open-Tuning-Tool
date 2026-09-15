with open("fpv_tuner/ui/pages/analysis_page.py", "r") as f:
    code = f.read()

target = """            step_responses=results.get("step_responses", {}),
            heatmaps=results.get("heatmaps", {}),
        ))"""

replacement = """            step_responses=results.get("step_responses", {}),
            heatmaps=results.get("heatmaps", {}),
            dterm_heatmaps=results.get("dterm_heatmaps", {}),
        ))"""

code = code.replace(target, replacement)

with open("fpv_tuner/ui/pages/analysis_page.py", "w") as f:
    f.write(code)
