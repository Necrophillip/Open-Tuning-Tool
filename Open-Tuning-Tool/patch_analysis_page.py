with open("fpv_tuner/ui/pages/analysis_page.py", "r") as f:
    code = f.read()

# We need to change where guess_optimal_pid or advisor.analyze is called.
if "mode=self.state.tuning_mode" not in code:
    code = code.replace("guess_optimal_pid(df, pids, headers, gyro_model=gyro_model)", "guess_optimal_pid(df, pids, headers, gyro_model=gyro_model, mode=self.state.tuning_mode)")
    with open("fpv_tuner/ui/pages/analysis_page.py", "w") as f:
        f.write(code)
