import re
import numpy as np
from fpv_tuner.analysis.utils import apply_smoothing

# A framework for storing drone characteristics. This allows the tuner to adapt
# its behavior based on the type of quadcopter being tuned.
DRONE_PROFILES = {
    "Default": {
        "inertia": 0.005,
        "safe_ranges": {
            'p_roll': (20, 150), 'i_roll': (20, 150), 'd_roll': (10, 100),
            'p_pitch': (20, 150), 'i_pitch': (20, 150), 'd_pitch': (10, 100),
            'p_yaw': (20, 150), 'i_yaw': (20, 150), 'd_yaw': (0, 50),
        }
    },
    "5-inch Freestyle": {
        "inertia": 0.005,
        "safe_ranges": {
            'p_roll': (40, 120), 'i_roll': (50, 130), 'd_roll': (30, 80),
            'p_pitch': (40, 130), 'i_pitch': (50, 140), 'd_pitch': (35, 90),
            'p_yaw': (40, 100), 'i_yaw': (50, 100), 'd_yaw': (0, 30),
        }
    },
    "Tinywhoop (1S)": {
        "inertia": 0.0008,
        "safe_ranges": {
            'p_roll': (20, 80), 'i_roll': (30, 90), 'd_roll': (20, 70),
            'p_pitch': (20, 85), 'i_pitch': (30, 95), 'd_pitch': (20, 75),
            'p_yaw': (30, 100), 'i_yaw': (40, 100), 'd_yaw': (0, 20),
        }
    },
     "Cinelifter": {
        "inertia": 0.015,
        "safe_ranges": {
            'p_roll': (50, 150), 'i_roll': (60, 160), 'd_roll': (40, 100),
            'p_pitch': (50, 160), 'i_pitch': (60, 170), 'd_pitch': (45, 110),
            'p_yaw': (50, 120), 'i_yaw': (50, 110), 'd_yaw': (0, 30),
        }
    }
}

def parse_dump(file_path):
    """
    Parses a Betaflight dump file to extract a comprehensive set of tuning parameters
    and the firmware version. It prioritizes settings under the active profile but
    also reads global settings.
    """
    TARGET_KEYS = {
        'p_roll', 'i_roll', 'd_roll', 'f_roll', 'p_pitch', 'i_pitch', 'd_pitch', 'f_pitch',
        'p_yaw', 'i_yaw', 'd_yaw', 'f_yaw',
    }
    settings = {}
    firmware_version = None
    active_profile_id = -1
    profile_settings = {}
    global_settings = {}

    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith('# Betaflight /'):
                firmware_version = stripped_line.strip('# ').strip()
            if stripped_line.startswith('profile '):
                active_profile_id = int(stripped_line.split(' ')[1])

        if active_profile_id == -1: active_profile_id = 0

        in_profile_block = False
        current_profile_id = -1
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith('# profile '):
                in_profile_block = True
                current_profile_id = int(stripped_line.split(' ')[2])
                continue
            if in_profile_block and (stripped_line.startswith('#') or not stripped_line):
                in_profile_block = False
                current_profile_id = -1
                continue
            match = re.match(r'set\s+([\w_]+)\s+=\s+([\w\d.-]+)', stripped_line)
            if not match: continue
            key, value = match.group(1), match.group(2)
            if key not in TARGET_KEYS: continue
            try:
                value = float(value) if '.' in value else int(value)
            except ValueError: pass
            if in_profile_block and current_profile_id == active_profile_id:
                profile_settings[key] = value
            else:
                global_settings[key] = value

        settings = global_settings.copy()
        settings.update(profile_settings)

    except FileNotFoundError:
        return None, None, f"Dump file not found at '{file_path}'"
    except Exception as e:
        return None, None, f"An error occurred while parsing: {e}"

    if not settings:
        return None, firmware_version, "Could not find any relevant tuning settings in the dump file."

    return settings, firmware_version, None

def propose_pids_from_simulation(base_pids, drone_profile):
    # Simplified version of the old slider logic
    pids = base_pids.copy()
    # A simple heuristic: slightly increase P and D for a more aggressive tune
    p_multiplier = 1.1
    d_multiplier = 1.1
    safe_ranges = drone_profile.get("safe_ranges", {})

    for axis in ['roll', 'pitch', 'yaw']:
        p_key, d_key = f'p_{axis}', f'd_{axis}'
        if p_key in pids:
            pids[p_key] = int(pids[p_key] * p_multiplier)
        if d_key in pids:
            pids[d_key] = int(pids[d_key] * d_multiplier)

    # Clamp to safe ranges
    for key, (min_val, max_val) in safe_ranges.items():
        if key in pids:
            pids[key] = np.clip(pids[key], min_val, max_val)

    return pids

def propose_pids_from_bbl_and_cli(current_pids, log_df, drone_profile, axis):
    """
    Proposes PIDs by comparing real BBL response to simulated CLI response.
    """
    # 1. Get real response from BBL
    real_time, real_response = extract_step_response_from_log(log_df, axis)
    if real_time is None: return current_pids # Fallback to current if no BBL data
    real_metrics = calculate_response_metrics(real_time, real_response)

    # 2. Get simulated response from current PIDs
    inertia = drone_profile.get("inertia", 0.005)
    sim_time, sim_response = simulate_step_response(current_pids, axis, inertia)
    if sim_time is None: return current_pids # Fallback
    sim_metrics = calculate_response_metrics(sim_time, sim_response)

    if not real_metrics or not sim_metrics or any(np.isnan(v) for v in real_metrics.values()) or any(np.isnan(v) for v in sim_metrics.values()):
        return current_pids # Fallback if metrics are bad

    # 3. Compare metrics and adjust PIDs
    overshoot_error = real_metrics.get("Overshoot (%)", 0) - sim_metrics.get("Overshoot (%)", 0)
    rise_time_error = real_metrics.get("Rise Time (s)", 1) - sim_metrics.get("Rise Time (s)", 1)

    proposed_pids = current_pids.copy()
    p_key, d_key = f'p_{axis}', f'd_{axis}'

    # Heuristics
    if overshoot_error > 5: # Real is more oscillatory
        proposed_pids[d_key] = int(proposed_pids.get(d_key, 40) * 1.1) # Increase D
    elif overshoot_error < -5: # Real is more damped
        proposed_pids[d_key] = int(proposed_pids.get(d_key, 40) * 0.9) # Decrease D

    if rise_time_error > 0.02: # Real is slower
        proposed_pids[p_key] = int(proposed_pids.get(p_key, 40) * 1.1) # Increase P
    elif rise_time_error < -0.02: # Real is faster
        proposed_pids[p_key] = int(proposed_pids.get(p_key, 40) * 0.9) # Decrease P

    # Clamp to safe ranges
    safe_ranges = drone_profile.get("safe_ranges", {})
    for key, (min_val, max_val) in safe_ranges.items():
        if key in proposed_pids:
            proposed_pids[key] = int(np.clip(proposed_pids[key], min_val, max_val))

    return proposed_pids

def simulate_step_response(pids, axis, inertia=0.005, duration=1.0, time_steps=1000):
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
        output = Kp * error + Ki * integral + Kd * derivative
        acceleration = output / inertia
        velocity += acceleration * dt
        position += velocity * dt
        response[i] = position
        prev_error = error

    return t, response

def propose_pids_from_metrics(metrics, drone_profile):
    if not metrics or any(np.isnan(v) for v in metrics.values()): return {}
    overshoot, rise_time = metrics.get("Overshoot (%)", 0), metrics.get("Rise Time (s)", 1.0)
    base_pids = {k: (v[0] + v[1]) // 2 for k, v in drone_profile.get("safe_ranges", {}).items()}
    p_mult = 1.2 if rise_time > 0.1 else 0.8 if rise_time < 0.04 else 1.0
    d_mult = 1.3 if overshoot > 15 else 0.8 if overshoot < 2 else 1.0
    for axis in ['roll', 'pitch', 'yaw']:
        if f'p_{axis}' in base_pids: base_pids[f'p_{axis}'] = int(base_pids[f'p_{axis}'] * p_mult)
        if f'd_{axis}' in base_pids: base_pids[f'd_{axis}'] = int(base_pids[f'd_{axis}'] * d_mult)
    return {k: np.clip(v, *drone_profile["safe_ranges"][k]) for k, v in base_pids.items() if k in drone_profile["safe_ranges"]}

def generate_cli(pids):
    if not pids: return "No PIDs proposed."
    cli = "# Paste into Betaflight CLI:\n"
    cli += "\n".join([f"set {k} = {v}" for k, v in pids.items() if k.startswith(('p_', 'i_', 'd_'))])
    cli += "\nsave\n"
    return cli

def calculate_response_metrics(time, response, setpoint=1.0):
    if response is None or len(response) < 2: return {}
    final_val_idx = int(len(response) * 0.9)
    final_val = np.mean(response[final_val_idx:])
    peak_val = np.max(response)
    overshoot = ((peak_val - final_val) / final_val) * 100 if final_val != 0 else 0
    try:
        t10 = time[np.where(response >= 0.1 * final_val)[0][0]]
        t90 = time[np.where(response >= 0.9 * final_val)[0][0]]
        rise_time = t90 - t10
    except (IndexError, ZeroDivisionError): rise_time = np.nan
    try:
        settling_thresh = 0.02 * abs(final_val)
        unsettled = np.where(np.abs(response - final_val) > settling_thresh)[0]
        settling_time = time[unsettled[-1]] if len(unsettled) > 0 else time[np.where(np.abs(response-final_val) <= settling_thresh)[0][0]]
    except (IndexError, ZeroDivisionError): settling_time = np.nan
    oscillation = np.sum(np.abs(response[np.where(time >= settling_time)[0][0]:] - final_val)) if not np.isnan(settling_time) else np.nan
    return {"Overshoot (%)": overshoot, "Rise Time (s)": rise_time, "Settling Time (s)": settling_time, "Oscillation": oscillation}

def classify_step_response(metrics):
    if not metrics or any(np.isnan(v) for v in metrics.values()): return "Unstable or Incomplete", "red"
    overshoot, oscillation, rise_time = metrics.get("Overshoot (%)",0), metrics.get("Oscillation",0), metrics.get("Rise Time (s)",1.0)
    if overshoot > 15 or oscillation > 10: return "Oscillatory / High Overshoot", "red"
    if overshoot > 5: return "Underdamped (noticeable overshoot)", "orange"
    if rise_time < 0.08: return "Critically Damped (Optimal)", "green"
    return "Slightly Overdamped (Slow)", "yellow"

def extract_step_response_from_log(df, axis, **kwargs):
    axis_map = {'roll': 0, 'pitch': 1, 'yaw': 2}
    if axis not in axis_map: return None, None
    rc_col, gyro_col, time_col = f'rcCommand[{axis_map[axis]}]', f'gyroADC[{axis_map[axis]}]', 'time (us)'
    if not all(c in df.columns for c in [rc_col, gyro_col, time_col]): return None, None

    df[gyro_col] = apply_smoothing(df[gyro_col], kwargs.get('smooth_factor', 5))
    rc_min, rc_max = df[rc_col].min(), df[rc_col].max()
    if rc_max == rc_min: return None, None
    rc_norm = 2 * (df[rc_col] - rc_min) / (rc_max - rc_min) - 1

    diff = rc_norm.diff().abs()
    candidates = df.index[diff > kwargs.get('step_threshold', 0.6)] # Relaxed threshold
    if len(candidates) == 0: return None, None

    valid_indices, last_time = [], -np.inf
    min_interval_us = kwargs.get('min_step_interval_s', 0.3) * 1_000_000 # Relaxed interval
    for idx in candidates:
        if df.loc[idx, time_col] > last_time + min_interval_us:
            valid_indices.append(idx)
            last_time = df.loc[idx, time_col]

    if not valid_indices: return None, None

    all_responses, final_time_s = [], None
    duration_s = kwargs.get('duration_s', 0.4)
    for start_idx in valid_indices:
        start_time = df.loc[start_idx, time_col]
        end_time = start_time + (duration_s * 1_000_000)
        win_df = df[(df[time_col] >= start_time) & (df[time_col] < end_time)]
        if len(win_df) < 2: continue

        time_s = (win_df[time_col] - start_time) / 1_000_000
        gyro_shifted = win_df[gyro_col] - win_df[gyro_col].iloc[0]
        rc_win = rc_norm.loc[win_df.index]
        step_mag = rc_win.iloc[-1] - rc_win.iloc[0]
        if abs(step_mag) < 1e-6: continue

        all_responses.append((gyro_shifted / step_mag).values)
        if final_time_s is None: final_time_s = time_s.values

    if not all_responses: return None, None

    max_len = max(len(r) for r in all_responses)
    padded = [np.pad(r, (0, max_len - len(r)), 'edge') for r in all_responses]
    avg_resp = np.median(np.vstack(padded), axis=0)

    time_vec = final_time_s[:len(avg_resp)] if final_time_s is not None else np.linspace(0, duration_s, len(avg_resp))
    return time_vec, avg_resp