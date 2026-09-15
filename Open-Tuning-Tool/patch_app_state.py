with open("fpv_tuner/ui/app_state.py", "r") as f:
    code = f.read()

code = code.replace("heatmaps: dict = field(default_factory=dict)", "heatmaps: dict = field(default_factory=dict)\n    dterm_heatmaps: dict = field(default_factory=dict)")

with open("fpv_tuner/ui/app_state.py", "w") as f:
    f.write(code)
