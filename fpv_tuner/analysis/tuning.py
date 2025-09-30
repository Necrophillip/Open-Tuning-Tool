import re
import numpy as np
from scipy.optimize import curve_fit
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

def first_order_step(t, K, tau):
    return K * (1 - np.exp(-t / tau))

def second_order_step(t, K, wn, zeta):
    # Ensure arguments are floats to avoid TypeError with numpy functions
    K, wn, zeta, t = float(K), float(wn), float(zeta), np.array(t, dtype=float)

    if zeta < 0: return np.zeros_like(t) * np.nan # Non-physical

    # Handle the three cases for a second-order system
    if np.isclose(zeta, 1): # Critically damped
        return K * (1 - (1 + wn * t) * np.exp(-wn * t))
    elif zeta > 1: # Overdamped
        # To avoid numerical instability, calculate two roots
        r1 = -wn * zeta + wn * np.sqrt(zeta**2 - 1)
        r2 = -wn * zeta - wn * np.sqrt(zeta**2 - 1)
        return K * (1 + (r2 * np.exp(r1 * t) - r1 * np.exp(r2 * t)) / (r1 - r2))
    else: # Underdamped
        wd = wn * np.sqrt(1 - zeta**2)
        phi = np.arccos(zeta)
        return K * (1 - (1 / np.sqrt(1 - zeta**2)) * np.exp(-zeta * wn * t) * np.sin(wd * t + phi))


def extract_step_response_from_log(df, axis):
    axis_map = {'roll': 0, 'pitch': 1, 'yaw': 2}
    rc_col = f'rcCommand[{axis_map.get(axis, -1)}]'
    gyro_col = f'gyroADC[{axis_map.get(axis, -1)}]'
    time_col = 'time (us)'

    if rc_col not in df.columns: return None

    time = df[time_col].to_numpy() * 1e-6
    rc = df[rc_col].to_numpy()
    gyro = df[gyro_col].to_numpy()
    dt = np.mean(np.diff(time))

    # --- Step 1: Detect large deflections ---
    thresh = 0.65 * np.max(np.abs(rc))
    deflex_mask = np.abs(rc) > thresh
    starts = np.where(np.diff(deflex_mask.astype(int)) == 1)[0]
    if len(starts) == 0: return None

    # --- Step 2: Extract initial window and normalize ---
    initial_responses = []
    for idx in starts:
        window = int(0.2 / dt) # 200ms window
        if idx + window >= len(time): continue
        t_win = time[idx:idx+window] - time[idx]
        y_win = gyro[idx:idx+window]
        delta_u = rc[idx+1] - rc[idx]
        if abs(delta_u) < 1e-6: continue
        y_norm = (y_win - y_win[0]) / delta_u
        initial_responses.append(y_norm)

    if not initial_responses: return None
    min_len = min(len(r) for r in initial_responses)
    t_avg_initial = time[:min_len] - time[0]
    y_avg_initial = np.mean([r[:min_len] for r in initial_responses], axis=0)

    # --- Step 3: First fit to estimate tau ---
    try:
        popt1_est, _ = curve_fit(first_order_step, t_avg_initial, y_avg_initial, p0=[1, 0.05])
        tau_est = popt1_est[1]
    except RuntimeError:
        tau_est = 0.05  # Fallback

    # --- Step 4: Redimension window to 2*tau and re-process ---
    final_responses = []
    window = int(max(0.1, 2 * tau_est) / dt) # Use at least 100ms
    for idx in starts:
        if idx + window >= len(time): continue
        t_win = time[idx:idx+window] - time[idx]
        y_win = gyro[idx:idx+window]
        delta_u = rc[idx+1] - rc[idx]
        if abs(delta_u) < 1e-6: continue
        y_norm = (y_win - y_win[0]) / delta_u
        final_responses.append(y_norm)

    if not final_responses: return None
    min_len = min(len(r) for r in final_responses)
    t_avg = time[:min_len] - time[0]
    y_avg = np.mean([r[:min_len] for r in final_responses], axis=0)

    # --- Final fits ---
    try:
        popt1, _ = curve_fit(first_order_step, t_avg, y_avg, p0=[1, tau_est], maxfev=5000)
        y_fit1 = first_order_step(t_avg, *popt1)
    except RuntimeError:
        popt1, y_fit1 = [np.nan, np.nan], np.zeros_like(t_avg)

    try:
        # Clip the initial guess for K to be within the defined bounds [0, 2]
        k_guess = np.clip(np.mean(y_avg[-5:]), 0.0, 2.0)
        p0_2nd_order = [k_guess, 200, 0.5]

        popt2, _ = curve_fit(second_order_step, t_avg, y_avg, p0=p0_2nd_order, maxfev=5000, bounds=([0, 0, 0], [2, 1000, 1.5]))
        y_fit2 = second_order_step(t_avg, *popt2)
    except RuntimeError:
        popt2, y_fit2 = [np.nan, np.nan, np.nan], np.zeros_like(t_avg)

    return {
        "t_avg": t_avg, "y_avg": y_avg,
        "y_fit1": y_fit1, "popt1": popt1,
        "y_fit2": y_fit2, "popt2": popt2,
    }