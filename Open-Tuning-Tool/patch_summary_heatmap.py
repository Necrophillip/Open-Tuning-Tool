with open("fpv_tuner/analysis/summary.py", "r") as f:
    code = f.read()

target = """def compute_noise_heatmap(df: pd.DataFrame, axis_name: str, n_throttle_bins: int = 80,
                          n_freq_bins: int = 256):
    \"\"\"
    Compute a throttle-vs-noise heatmap for one gyro axis.

    Returns ``{"throttle", "freq", "heatmap"}`` or None.
    \"\"\"
    idx = AXES.index(axis_name)
    time_col = _find_time_col(df)
    noise_col = f"gyroADC[{idx}]\""""

replacement = """def compute_noise_heatmap(df: pd.DataFrame, axis_name: str, n_throttle_bins: int = 80,
                          n_freq_bins: int = 256, col_prefix: str = "gyroADC"):
    \"\"\"
    Compute a throttle-vs-noise heatmap for a given signal prefix (gyroADC, axisD, etc).

    Returns ``{"throttle", "freq", "heatmap"}`` or None.
    \"\"\"
    idx = AXES.index(axis_name)
    time_col = _find_time_col(df)
    noise_col = f"{col_prefix}[{idx}]\""""

code = code.replace(target, replacement)
with open("fpv_tuner/analysis/summary.py", "w") as f:
    f.write(code)
