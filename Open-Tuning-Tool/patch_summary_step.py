with open("fpv_tuner/analysis/summary.py", "r") as f:
    code = f.read()

target = """    est_fs = _estimate_loop_hz(df, time_col)
    try:
        analysis = analyze_step_response(
            df[time_col].to_numpy(dtype=np.int64),
            setpoint,
            df[gyro_col].to_numpy(),
            pid_loop_hz=est_fs,
            plot=False,
            return_fit_curve=True,
        )"""

replacement = """    est_fs = _estimate_loop_hz(df, time_col)
    
    motor_cols = [c for c in df.columns if c.startswith("motor[") and "]" in c]
    motor_signals = [df[c].to_numpy() for c in motor_cols] if motor_cols else None
    
    try:
        analysis = analyze_step_response(
            df[time_col].to_numpy(dtype=np.int64),
            setpoint,
            df[gyro_col].to_numpy(),
            pid_loop_hz=est_fs,
            plot=False,
            return_fit_curve=True,
            motor_signals=motor_signals,
        )"""

code = code.replace(target, replacement)

with open("fpv_tuner/analysis/summary.py", "w") as f:
    f.write(code)
