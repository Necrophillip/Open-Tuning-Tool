with open("fpv_tuner/ui/pages/tuning_page.py", "r") as f:
    code = f.read()

target = "recommendation = advisor.analyze(df, pids, context_headers, gyro_model=gyro_model)"
replacement = "recommendation = advisor.analyze(df, pids, context_headers, gyro_model=gyro_model, mode=self.state.tuning_mode)"

if target in code:
    code = code.replace(target, replacement)
    with open("fpv_tuner/ui/pages/tuning_page.py", "w") as f:
        f.write(code)
