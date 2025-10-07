import numpy as np
from fpv_tuner.analysis.utils import apply_smoothing

DRONE_PROFILES = {
    "Default": {"inertia": 0.005},
    "5-inch Freestyle": {"inertia": 0.005},
    "Tinywhoop (1S)": {"inertia": 0.0008},
    "Cinelifter": {"inertia": 0.015},
}

# Baseline PID profiles for different types of drones.
# These are used to provide a reasonable starting point when tuning from a CLI dump without blackbox data.
BASELINE_PIDS = {
    "Default":           {'p_roll': 45, 'i_roll': 85, 'd_roll': 38, 'f_roll': 90, 'p_pitch': 55, 'i_pitch': 90, 'd_pitch': 42, 'f_pitch': 95, 'p_yaw': 70, 'i_yaw': 45, 'd_yaw': 0, 'f_yaw': 85},
    "5-inch Freestyle":  {'p_roll': 45, 'i_roll': 85, 'd_roll': 38, 'f_roll': 90, 'p_pitch': 55, 'i_pitch': 90, 'd_pitch': 42, 'f_pitch': 95, 'p_yaw': 70, 'i_yaw': 45, 'd_yaw': 0, 'f_yaw': 85},
    "Tinywhoop (1S)":    {'p_roll': 60, 'i_roll': 70, 'd_roll': 55, 'f_roll': 60, 'p_pitch': 65, 'i_pitch': 75, 'd_pitch': 60, 'f_pitch': 65, 'p_yaw': 80, 'i_yaw': 45, 'd_yaw': 0, 'f_yaw': 80},
    "Cinelifter":        {'p_roll': 35, 'i_roll': 70, 'd_roll': 30, 'f_roll': 70, 'p_pitch': 40, 'i_pitch': 75, 'd_pitch': 35, 'f_pitch': 75, 'p_yaw': 60, 'i_yaw': 45, 'd_yaw': 0, 'f_yaw': 60},
}

def get_step_response(df, axis, step_threshold_ratio=0.65, duration_s=0.8, pre_step_s=0.05, smooth_factor=5):
    """
    Extracts a single, most prominent step response from a blackbox log,
    including a pre-step period for context. Returns the raw gyro response.
    """
    axis_map = {'roll': 0, 'pitch': 1, 'yaw': 2}
    rc_col = f'rcCommand[{axis_map.get(axis, -1)}]'
    gyro_col = f'gyroADC[{axis_map.get(axis, -1)}]'
    time_col = 'time (us)'

    if not all(c in df.columns for c in [rc_col, gyro_col, time_col]):
        return None

    time_us = df[time_col].to_numpy()
    rc_raw = df[rc_col].to_numpy()
    gyro_raw = df[gyro_col].to_numpy()
    dt = np.mean(np.diff(time_us)) * 1e-6 if len(time_us) > 1 else 0.001

    if dt == 0: return None

    gyro_smoothed = apply_smoothing(gyro_raw, smooth_factor)
    rc_rate_of_change = np.diff(rc_raw)
    if len(rc_rate_of_change) == 0: return None

    step_idx = np.argmax(np.abs(rc_rate_of_change))

    pre_step_samples = int(pre_step_s / dt)
    window_samples = int(duration_s / dt)
    start_idx = step_idx - pre_step_samples
    end_idx = step_idx + window_samples

    if start_idx < 0 or end_idx >= len(gyro_smoothed):
        return None

    pre_win = rc_raw[max(0, step_idx - 5) : step_idx]
    post_win = rc_raw[step_idx + 1 : step_idx + 6]
    if len(pre_win) == 0 or len(post_win) == 0: return None

    setpoint = np.mean(post_win) - np.mean(pre_win)
    if abs(setpoint) < 1e-6: return None

    gyro_win = gyro_smoothed[start_idx:end_idx]
    gyro_shifted = gyro_win - np.mean(gyro_smoothed[start_idx : step_idx])

    time_vector = np.linspace(-pre_step_s, duration_s, len(gyro_win), endpoint=False)

    return {"time": time_vector, "response": gyro_shifted, "setpoint": setpoint}

def calculate_response_metrics(time, response, setpoint):
    if response is None or len(response) < 2: return {}

    final_value = setpoint
    peak_value = np.max(response) if setpoint > 0 else np.min(response)
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
            settling_time = time[0]
        else:
            last_unsettled_index = unsettled_indices[-1]
            if last_unsettled_index + 1 < len(time):
                settling_time = time[last_unsettled_index + 1]
            else:
                settling_time = np.nan
    except (IndexError, ZeroDivisionError): settling_time = np.nan

    return {"Overshoot (%)": overshoot, "Rise Time (s)": rise_time, "Settling Time (s)": settling_time}

def classify_step_response(metrics):
    if not metrics or any(np.isnan(v) for v in metrics.values()): return "Incomplete Data", "gray"
    overshoot = metrics.get("Overshoot (%)", 0)
    rise_time = metrics.get("Rise Time (s)", 1.0)
    if overshoot > 20: return "Very Oscillatory", "red"
    if overshoot > 10: return "Oscillatory", "orange"
    if rise_time < 0.08: return "Responsive", "green"
    if rise_time > 0.2: return "Sluggish", "blue"
    return "Acceptable", "white"

def suggest_pid_changes(pids, metrics, axis, is_cli_only=False, profile_name="Default"):
    """
    Suggests new PID values.
    If is_cli_only is True, it suggests a baseline tune for the given profile.
    Otherwise, it suggests changes based on step response metrics.
    """
    suggested_pids = pids.copy()

    if is_cli_only:
        baseline = BASELINE_PIDS.get(profile_name, BASELINE_PIDS["Default"])
        for term in ['p', 'i', 'd', 'f']:
            key = f"{term}_{axis}"
            if key in baseline:
                suggested_pids[key] = baseline[key]
        return suggested_pids

    if not metrics: return suggested_pids

    overshoot = metrics.get("Overshoot (%)", 0)
    rise_time = metrics.get("Rise Time (s)", 1.0)

    p_key, d_key = f'p_{axis}', f'd_{axis}'

    if overshoot > 15:
        suggested_pids[p_key] = int(pids.get(p_key, 50) * 0.9)
        suggested_pids[d_key] = int(pids.get(d_key, 30) * 1.1)
    elif rise_time > 0.15:
        suggested_pids[p_key] = int(pids.get(p_key, 50) * 1.1)
    elif overshoot < 2:
        suggested_pids[d_key] = int(pids.get(d_key, 30) * 0.9)

    return suggested_pids

def simulate_step_response(pids, axis, inertia, duration=0.8, time_steps=1000):
    P_SCALE, I_SCALE, D_SCALE = 0.01, 0.005, 0.0001
    Kp = pids.get(f'p_{axis}', 0) * P_SCALE
    Ki = pids.get(f'i_{axis}', 0) * I_SCALE
    Kd = pids.get(f'd_{axis}', 0) * D_SCALE

    dt = duration / time_steps
    t = np.linspace(0, duration, time_steps)
    setpoint, position, velocity, integral, prev_error = 1.0, 0.0, 0.0, 0.0, 0.0
    response = np.zeros(time_steps)

    for i in range(time_steps):
        error = setpoint - position
        integral += error * dt
        derivative = (error - prev_error) / dt
        controller_output = (Kp * error) + (Ki * integral) + (Kd * derivative)
        acceleration = controller_output / inertia
        velocity += acceleration * dt
        position += velocity * dt
        response[i] = position
        prev_error = error

    return t, response

def generate_cli(pids, axis):
    commands = f"# Suggestions for {axis.capitalize()} Axis\n"
    for term in ['p', 'i', 'd', 'f']:
        key = f"{term}_{axis}"
        if key in pids:
            commands += f"set {key} = {pids[key]}\n"
    commands += "save\n"
    return commands