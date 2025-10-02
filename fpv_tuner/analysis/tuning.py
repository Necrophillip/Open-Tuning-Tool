import numpy as np
from fpv_tuner.analysis.utils import apply_smoothing

def get_step_response(df, axis, step_threshold_ratio=0.65, duration_s=0.4, smooth_factor=5):
    """
    Extracts and averages multiple step response sequences from a blackbox log
    to produce a single, robust step response curve.
    """
    axis_map = {'roll': 0, 'pitch': 1, 'yaw': 2}
    rc_col = f'rcCommand[{axis_map.get(axis, -1)}]'
    gyro_col = f'gyroADC[{axis_map.get(axis, -1)}]'
    time_col = 'time (us)'

    if not all(c in df.columns for c in [rc_col, gyro_col, time_col]):
        return None, None

    # --- Convert to numpy arrays for direct processing ---
    time_us = df[time_col].to_numpy()
    rc_raw = df[rc_col].to_numpy()
    gyro_raw = df[gyro_col].to_numpy()
    dt = np.mean(np.diff(time_us)) * 1e-6 if len(time_us) > 1 else 0.001

    if dt == 0: return None, None

    # --- Pre-filter gyro data ---
    gyro_smoothed = apply_smoothing(gyro_raw, smooth_factor)

    # --- Step 1: Detect all potential step starts ---
    max_deflection = np.max(np.abs(rc_raw))
    if max_deflection == 0: return None, None

    threshold = step_threshold_ratio * max_deflection
    deflex_mask = np.abs(rc_raw) > threshold
    starts = np.where(np.diff(deflex_mask.astype(int)) == 1)[0]
    if len(starts) == 0: return None, None

    # --- Step 2: Iterate through all candidates and collect valid responses ---
    all_responses = []
    window_samples = int(duration_s / dt) if dt > 0 else 0

    for idx in starts:
        if idx + window_samples >= len(gyro_smoothed) or idx + 1 >= len(rc_raw):
            continue

        # Robustly calculate delta_u by averaging before and after the step
        pre_step_window = rc_raw[max(0, idx - 5) : idx]
        post_step_window = rc_raw[idx + 1 : idx + 6]

        if len(pre_step_window) == 0 or len(post_step_window) == 0:
            continue

        pre_step_avg = np.mean(pre_step_window)
        post_step_avg = np.mean(post_step_window)
        delta_u = post_step_avg - pre_step_avg

        if abs(delta_u) < 1e-6: continue

        gyro_win = gyro_smoothed[idx : idx + window_samples]
        gyro_shifted = gyro_win - gyro_win[0]
        response_normalized = gyro_shifted / delta_u

        all_responses.append(response_normalized)

    # --- Step 3: If any valid responses were found, average them ---
    if not all_responses:
        return None, None

    min_len = min(len(r) for r in all_responses)
    all_responses_trimmed = [r[:min_len] for r in all_responses]

    response_stack = np.vstack(all_responses_trimmed)
    averaged_response = np.mean(response_stack, axis=0)
    final_time_vector = np.linspace(0, (min_len - 1) * dt, min_len)

    return final_time_vector, averaged_response

def calculate_response_metrics(time, response, setpoint=1.0):
    if response is None or len(response) < 2: return {}
    final_value_start_index = int(len(response) * 0.9)
    final_value = np.mean(response[final_value_start_index:])
    if np.isclose(final_value, 0): final_value = 1.0
    peak_value = np.max(response)
    overshoot = ((peak_value - final_value) / final_value) * 100 if final_value != 0 else 0
    try:
        ten_percent_val = 0.1 * final_value
        ninety_percent_val = 0.9 * final_value
        time_at_10 = time[np.where(response >= ten_percent_val)[0][0]]
        time_at_90 = time[np.where(response >= ninety_percent_val)[0][0]]
        rise_time = time_at_90 - time_at_10
    except (IndexError, ZeroDivisionError): rise_time = np.nan
    try:
        settling_threshold = 0.05 * abs(final_value)
        unsettled_indices = np.where(np.abs(response - final_value) > settling_threshold)[0]

        if len(unsettled_indices) == 0:
            # If it's always settled, find when it first entered the band.
            # This is a bit arbitrary, but time[0] is a safe default.
            settling_time = time[0]
        else:
            # The settling time is the time of the sample *after* the last unsettled point.
            last_unsettled_index = unsettled_indices[-1]
            if last_unsettled_index + 1 < len(time):
                settling_time = time[last_unsettled_index + 1]
            else: # The last point was unsettled, so it never truly settled.
                settling_time = np.nan
    except (IndexError, ZeroDivisionError):
        settling_time = np.nan
    oscillation = 0
    if not np.isnan(settling_time):
        try:
            settling_index = np.where(time >= settling_time)[0][0]
            oscillation = np.sum(np.abs(response[settling_index:] - final_value))
        except IndexError: oscillation = np.nan
    return {"Overshoot (%)": overshoot, "Rise Time (s)": rise_time, "Settling Time (s)": settling_time, "Oscillation": oscillation}

def classify_step_response(metrics):
    if not metrics or any(np.isnan(v) for v in metrics.values()): return "Incomplete Data", "gray"
    overshoot = metrics.get("Overshoot (%)", 0)
    rise_time = metrics.get("Rise Time (s)", 1.0)
    if overshoot > 20: return "Very Oscillatory", "red"
    if overshoot > 10: return "Oscillatory", "orange"
    if rise_time < 0.08: return "Responsive", "green"
    if rise_time > 0.2: return "Sluggish", "blue"
    return "Acceptable", "white"