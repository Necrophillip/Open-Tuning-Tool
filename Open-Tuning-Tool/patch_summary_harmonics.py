import re

with open("fpv_tuner/analysis/summary.py", "r") as f:
    code = f.read()

# Add import
if "from fpv_tuner.analysis.harmonics import compute_motor_harmonics" not in code:
    code = code.replace("from fpv_tuner.analysis.noise import calculate_throttle_noise_heatmap",
                        "from fpv_tuner.analysis.noise import calculate_throttle_noise_heatmap\\nfrom fpv_tuner.analysis.harmonics import compute_motor_harmonics")

# Update signature
target_sig = """def compute_noise_heatmap(df: pd.DataFrame, axis_name: str, n_throttle_bins: int = 80,
                          n_freq_bins: int = 256, col_prefix: str = "gyroADC"):"""
replacement_sig = """def compute_noise_heatmap(df: pd.DataFrame, axis_name: str, n_throttle_bins: int = 80,
                          n_freq_bins: int = 256, col_prefix: str = "gyroADC", motor_poles: int = 14):"""
code = code.replace(target_sig, replacement_sig)

# Update return logic
target_ret = """    if tc is None or hm is None:
        return None
    return {"throttle": tc, "freq": fb, "heatmap": hm}"""

replacement_ret = """    if tc is None or hm is None:
        return None
        
    result = {"throttle": tc, "freq": fb, "heatmap": hm}
    
    # Overlay Harmonics calculation
    harmonics_df = compute_motor_harmonics(df, motor_poles, time_col)
    if harmonics_df is not None:
        # Interpolate against throttle
        # We need raw throttle without clipping to map properly, but 'throttle' series is already 0-100
        valid_idx = throttle.notna() & harmonics_df['h1_hz'].notna()
        t_clean = throttle[valid_idx].values
        
        if len(t_clean) > 0:
            sort_idx = np.argsort(t_clean)
            t_sorted = t_clean[sort_idx]
            
            for h_col, key in [('h1_hz', 'h1'), ('h2_hz', 'h2'), ('h3_hz', 'h3')]:
                h_vals = harmonics_df[h_col][valid_idx].values
                h_sorted = h_vals[sort_idx]
                binned_h = np.interp(tc, t_sorted, h_sorted)
                result[key] = binned_h

    return result"""

code = code.replace(target_ret, replacement_ret)

with open("fpv_tuner/analysis/summary.py", "w") as f:
    f.write(code)
