import re
import numpy as np
from scipy.signal import lti, step

def parse_dump(file_path):
    """
    Parses a Betaflight dump file to extract a comprehensive set of tuning parameters
    and the firmware version. It prioritizes settings under the active profile but
    also reads global settings.
    """

    # Comprehensive list of parameters we want to extract
    TARGET_KEYS = {
        # PIDs and Feedforward
        'p_roll', 'i_roll', 'd_roll', 'f_roll',
        'p_pitch', 'i_pitch', 'd_pitch', 'f_pitch',
        'p_yaw', 'i_yaw', 'd_yaw', 'f_yaw',
        # Gyro Filters
        'gyro_lpf1_type', 'gyro_lpf1_static_hz', 'gyro_lpf1_dyn_min_hz', 'gyro_lpf1_dyn_max_hz',
        'gyro_lpf2_type', 'gyro_lpf2_static_hz',
        'gyro_notch1_hz', 'gyro_notch1_cutoff',
        'gyro_notch2_hz', 'gyro_notch2_cutoff',
        # D-Term Filters
        'dterm_lpf1_type', 'dterm_lpf1_static_hz', 'dterm_lpf1_dyn_min_hz', 'dterm_lpf1_dyn_max_hz',
        'dterm_lpf2_type', 'dterm_lpf2_static_hz',
        'dterm_notch_hz', 'dterm_notch_cutoff',
        # RC Smoothing
        'rc_smoothing_setpoint_cutoff', 'rc_smoothing_feedforward_cutoff', 'rc_smoothing_throttle_cutoff'
    }

    settings = {}
    firmware_version = None
    active_profile_id = -1
    profile_settings = {}
    global_settings = {}

    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        # Find the active profile ID and firmware version first
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith('# Betaflight /'):
                firmware_version = stripped_line.strip('# ').strip()
            if stripped_line.startswith('profile '):
                active_profile_id = int(stripped_line.split(' ')[1])

        if active_profile_id == -1: active_profile_id = 0

        # Parse the entire file for settings
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
            if not match:
                continue

            key, value = match.group(1), match.group(2)

            if key not in TARGET_KEYS:
                continue

            try:
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value)
            except ValueError:
                pass

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


# A framework for storing drone characteristics. This allows the tuner to adapt
# its behavior based on the type of quadcopter being tuned.
DRONE_PROFILES = {
    "Default": {
        "inertia": 0.005,
        "fitness_weights": {"overshoot": 2.0, "settling": 1.0, "rise_time": 0.5, "oscillation": 1.5},
        "safe_ranges": {
            'p_roll': (20, 150), 'i_roll': (20, 150), 'd_roll': (10, 100),
            'p_pitch': (20, 150), 'i_pitch': (20, 150), 'd_pitch': (10, 100),
            'p_yaw': (20, 150), 'i_yaw': (20, 150), 'd_yaw': (0, 50),
        }
    },
    "5-inch Freestyle": {
        "inertia": 0.005,
        "fitness_weights": {"overshoot": 1.5, "settling": 1.0, "rise_time": 1.0, "oscillation": 1.0},
        "safe_ranges": {
            'p_roll': (40, 120), 'i_roll': (50, 130), 'd_roll': (30, 80),
            'p_pitch': (40, 130), 'i_pitch': (50, 140), 'd_pitch': (35, 90),
            'p_yaw': (40, 100), 'i_yaw': (50, 100), 'd_yaw': (0, 30),
        }
    },
    "Tinywhoop (1S)": {
        "inertia": 0.0008,
        "fitness_weights": {"overshoot": 2.5, "settling": 1.5, "rise_time": 0.5, "oscillation": 2.0},
        "safe_ranges": {
            'p_roll': (20, 80), 'i_roll': (30, 90), 'd_roll': (20, 70),
            'p_pitch': (20, 85), 'i_pitch': (30, 95), 'd_pitch': (20, 75),
            'p_yaw': (30, 100), 'i_yaw': (40, 100), 'd_yaw': (0, 20),
        }
    },
     "Cinelifter": {
        "inertia": 0.015,
        "fitness_weights": {"overshoot": 3.0, "settling": 2.0, "rise_time": 0.2, "oscillation": 2.5},
        "safe_ranges": {
            'p_roll': (50, 150), 'i_roll': (60, 160), 'd_roll': (40, 100),
            'p_pitch': (50, 160), 'i_pitch': (60, 170), 'd_pitch': (45, 110),
            'p_yaw': (50, 120), 'i_yaw': (50, 110), 'd_yaw': (0, 30),
        }
    }
}


def validate_settings(proposed_pids, original_pids, drone_profile):
    """
    Validates proposed PIDs against relative and absolute safe ranges.
    Returns a list of warning strings.
    """
    warnings = []
    safe_ranges = drone_profile.get("safe_ranges", {})

    # Relative (multiplier) checks
    for key in proposed_pids:
        if key in original_pids and original_pids[key] > 0 and key.startswith(('p_', 'i_', 'd_')):
            ratio = proposed_pids[key] / original_pids[key]
            if not (0.5 <= ratio <= 1.7):
                warnings.append(
                    f"'{key}' ({proposed_pids[key]}) is {ratio:.2f}x the original value. "
                    f"(Recommended range: 0.5x - 1.7x)"
                )

    # Absolute (hard limit) checks
    for key, (min_val, max_val) in safe_ranges.items():
        if key in proposed_pids:
            value = proposed_pids[key]
            if not isinstance(value, (int, float)):
                continue
            if not min_val <= value <= max_val:
                warnings.append(
                    f"'{key}' ({value}) is outside the profile's absolute "
                    f"safe range of ({min_val} - {max_val})."
                )
    return warnings


def propose_tune(pids, reduction_percent=15):
    """
    DEPRECATED: This is a simple proposal method. Use find_optimal_tune for a better approach.
    Proposes new PID settings based on a percentage reduction for D-gains.
    Returns a dictionary with the proposed new values.
    """
    new_pids = pids.copy()
    if 'd_roll' in pids:
        new_pids['d_roll'] = int(pids['d_roll'] * (1 - reduction_percent / 100))
    if 'd_pitch' in pids:
        new_pids['d_pitch'] = int(pids['d_pitch'] * (1 - reduction_percent / 100))
    return new_pids


def _calculate_fitness(metrics, weights):
    """
    Calculates a fitness score from a metrics dictionary. Lower is better.
    """
    if not metrics:
        return float('inf')

    # Penalize heavily for instability (NaN values or extreme overshoot)
    if np.isnan(metrics.get("Settling Time (s)", 0)) or metrics.get("Overshoot (%)", 100) > 100:
        return float('inf')

    score = (
        metrics.get("Overshoot (%)", 50) * weights.get("overshoot", 1.0) +
        metrics.get("Settling Time (s)", 1) * 100 * weights.get("settling", 1.0) +
        metrics.get("Rise Time (s)", 1) * 100 * weights.get("rise_time", 1.0) +
        metrics.get("Oscillation", 100) * weights.get("oscillation", 1.0)
    )
    return score


def _compute_pids_from_sliders(base_pids, sliders):
    """Applies slider multipliers to a set of base PID values."""
    pids = base_pids.copy()
    m = sliders.get("master", 1.0)
    t = sliders.get("tracking", 1.0)
    drift = sliders.get("drift", 1.0)
    damp = sliders.get("damp", 1.0)
    ff = sliders.get("ff", 1.0)

    for axis in ["roll", "pitch", "yaw"]:
        pids[f'p_{axis}'] = int(m * t * base_pids.get(f'p_{axis}', 0))
        pids[f'i_{axis}'] = int(m * t * drift * base_pids.get(f'i_{axis}', 0))
        pids[f'd_{axis}'] = int(m * damp * base_pids.get(f'd_{axis}', 0))
        pids[f'f_{axis}'] = int(m * ff * base_pids.get(f'f_{axis}', 0))

    return pids

def tune_with_sliders(base_pids, drone_profile, axis_to_tune, iterations=50):
    """
    Uses a heuristic-based iterative approach to find a good set of sliders.
    """
    sliders = {"master": 1.0, "tracking": 1.0, "drift": 1.0, "damp": 1.0, "ff": 1.0}

    # Get parameters from the selected drone profile
    inertia = drone_profile.get("inertia", 0.005)

    # Define target metrics (can be moved to profile later)
    target_metrics = {"Overshoot (%)": 5, "Rise Time (s)": 0.05}

    # Small increments for slider adjustments
    STEP = 0.02

    for i in range(iterations):
        current_pids = _compute_pids_from_sliders(base_pids, sliders)

        # Validate the new PIDs
        warnings = validate_settings(current_pids, drone_profile)
        if warnings:
            print(f"Iteration {i}: Unsafe PIDs generated, stopping.")
            break # Stop if we've gone into an unsafe region

        sim_results = simulate_step_response(current_pids, axis=axis_to_tune, inertia=inertia, noise_level=0.05)
        if not sim_results:
            continue

        metrics = calculate_response_metrics(sim_results["time"], sim_results["response"])
        if not metrics or np.isnan(metrics.get("Overshoot (%)", 0)):
            continue

        # Heuristic adjustment logic based on user's pseudocode
        overshoot = metrics.get("Overshoot (%)", 0)
        rise_time = metrics.get("Rise Time (s)", 1.0)

        # This is a simplified heuristic model. A real implementation would be more complex.
        if overshoot > target_metrics["Overshoot (%)"] * 1.2: # more than 20% over target
            sliders["damp"] += STEP
            sliders["tracking"] -= STEP * 0.5 # Reduce P/I slightly to help with overshoot
        elif overshoot < target_metrics["Overshoot (%)"] * 0.8: # too sluggish
             sliders["damp"] -= STEP

        if rise_time > target_metrics["Rise Time (s)"] * 1.2:
            sliders["master"] += STEP
        elif rise_time < target_metrics["Rise Time (s)"] * 0.8:
            sliders["master"] -= STEP * 0.5

        # Clamp sliders to a reasonable range to prevent runaway
        for key in sliders:
            sliders[key] = np.clip(sliders[key], 0.5, 2.0)

    final_pids = _compute_pids_from_sliders(base_pids, sliders)
    return final_pids, sliders


def find_optimal_tune(initial_pids, drone_profile, axis_to_tune, mode='RP', iterations=50):
    """
    DEPRECATED: This function directly modifies PID values. The new approach is tune_with_sliders.
    Uses a simple hill-climbing algorithm to find a better PID tune.
    """
    best_pids = initial_pids.copy()

    # Get parameters from the selected drone profile
    inertia = drone_profile.get("inertia", 0.005)
    fitness_weights = drone_profile.get("fitness_weights", {})

    # Run a baseline simulation to get the initial fitness score
    sim_results = simulate_step_response(best_pids, axis=axis_to_tune, inertia=inertia, noise_level=0.05)
    if not sim_results:
        return initial_pids # Cannot simulate, return original

    metrics = calculate_response_metrics(sim_results["time"], sim_results["response"])
    best_fitness = _calculate_fitness(metrics, fitness_weights)

    # Determine which parameters to tweak based on the mode
    if mode == 'RPY':
        params_to_tweak = ['p_roll', 'd_roll', 'p_pitch', 'd_pitch', 'p_yaw', 'd_yaw']
    else: # Default to 'RP'
        params_to_tweak = ['p_roll', 'd_roll', 'p_pitch', 'd_pitch']

    for _ in range(iterations):
        candidate_pids = best_pids.copy()

        param_to_tweak = np.random.choice(params_to_tweak)
        adjustment = np.random.randint(-3, 4) # Adjust by a value between -3 and +3

        candidate_pids[param_to_tweak] += adjustment

        # Validate the new candidate against the profile's safe ranges
        warnings = validate_settings(candidate_pids, drone_profile)
        if warnings:
            continue

        # Simulate and calculate fitness for the candidate
        sim_results = simulate_step_response(candidate_pids, axis=axis_to_tune, inertia=inertia, noise_level=0.05)
        if not sim_results:
            continue

        metrics = calculate_response_metrics(sim_results["time"], sim_results["response"])
        candidate_fitness = _calculate_fitness(metrics, fitness_weights)

        # If the candidate is better, it becomes the new best
        if candidate_fitness < best_fitness:
            best_fitness = candidate_fitness
            best_pids = candidate_pids

    return best_pids


def generate_cli(pids):
    """
    Generates Betaflight CLI commands to set the given PID values.
    """
    cli_commands = "# Paste the following commands into the Betaflight CLI:\n"
    # Assuming we are targeting the active profile, no need for `profile X` command

    if 'p_roll' in pids: cli_commands += f"set p_roll = {pids['p_roll']}\n"
    if 'i_roll' in pids: cli_commands += f"set i_roll = {pids['i_roll']}\n"
    if 'd_roll' in pids: cli_commands += f"set d_roll = {pids['d_roll']}\n"
    if 'f_roll' in pids: cli_commands += f"set f_roll = {pids['f_roll']}\n"

    if 'p_pitch' in pids: cli_commands += f"\nset p_pitch = {pids['p_pitch']}\n"
    if 'i_pitch' in pids: cli_commands += f"set i_pitch = {pids['i_pitch']}\n"
    if 'd_pitch' in pids: cli_commands += f"set d_pitch = {pids['d_pitch']}\n"
    if 'f_pitch' in pids: cli_commands += f"set f_pitch = {pids['f_pitch']}\n"

    cli_commands += "\nsave\n"
    return cli_commands


def simulate_step_response(pids, axis, inertia=0.005, duration=1.0, time_steps=1000, noise_level=0.0,
                         disturbance_magnitude=0.0, disturbance_time=0.0):
    """
    Simulates the step response of a PID controller using a discrete-time loop.
    This allows for the injection of noise and other non-linearities.

    Args:
        pids (dict): A dictionary containing keys like 'p_roll', 'd_roll'.
        axis (str): The axis to simulate ('roll', 'pitch', 'yaw').
        inertia (float): An arbitrary inertia value for the system model.
        duration (float): The duration of the simulation in seconds.
        time_steps (int): The number of time steps in the simulation.
        noise_level (float): The standard deviation of the Gaussian noise to add to the gyro.
        disturbance_magnitude (float): The magnitude of the disturbance force.
        disturbance_time (float): The time at which to apply the disturbance.

    Returns:
        A tuple (time, response, d_term_trace) or (None, None, None) if PIDs are missing.
    """
    P_SCALE = 0.01
    I_SCALE = 0.005
    D_SCALE = 0.0001

    try:
        Kp = pids.get(f'p_{axis}', 0) * P_SCALE
        Ki = pids.get(f'i_{axis}', 0) * I_SCALE
        Kd = pids.get(f'd_{axis}', 0) * D_SCALE
    except (KeyError, TypeError):
         return None, None, None

    # Simulation parameters
    dt = duration / time_steps
    t = np.linspace(0, duration, time_steps)
    setpoint = 1.0  # Step input

    # System state variables
    position = 0.0
    velocity = 0.0

    # PID state variables
    integral = 0.0
    previous_error = 0.0

    # Filter state variables
    d_term_filtered = 0.0

    # Calculate PT1 filter alpha if applicable
    d_lpf_hz = pids.get('dterm_lpf1_static_hz', 0)
    if d_lpf_hz > 0:
        rc = 1 / (2 * np.pi * d_lpf_hz)
        d_lpf_alpha = dt / (dt + rc)
    else:
        d_lpf_alpha = 1.0 # No filtering

    # Output arrays
    response = np.zeros(time_steps)
    p_trace = np.zeros(time_steps)
    i_trace = np.zeros(time_steps)
    d_trace = np.zeros(time_steps)

    for i in range(time_steps):
        # Add noise to the measurement of the position (simulating noisy gyro)
        measured_position = position + np.random.normal(0, noise_level)

        # PID Calculation
        error = setpoint - measured_position
        integral += error * dt

        # Raw derivative
        derivative = (error - previous_error) / dt

        # Apply PT1 low-pass filter to the derivative
        d_term_filtered += d_lpf_alpha * (derivative - d_term_filtered)

        p_term = Kp * error
        i_term = Ki * integral
        d_term = Kd * d_term_filtered # Use the filtered value

        controller_output = p_term + i_term + d_term

        # Update system dynamics (plant)
        acceleration = controller_output / inertia

        # Apply disturbance if applicable
        if disturbance_magnitude > 0 and disturbance_time > 0 and \
           disturbance_time <= t[i] < disturbance_time + dt:
            acceleration += disturbance_magnitude / inertia

        velocity += acceleration * dt
        position += velocity * dt

        # Store results
        response[i] = position
        p_trace[i] = p_term
        i_trace[i] = i_term
        d_trace[i] = d_term

        # Update state for next iteration
        previous_error = error

    # Return a dictionary for clarity
    return {
        "time": t, "response": response, "p_trace": p_trace,
        "i_trace": i_trace, "d_trace": d_trace
    }


def calculate_response_metrics(time, response, setpoint=1.0):
    """
    Calculates key performance metrics from a step response trace.
    """
    if response is None or len(response) == 0:
        return {}

    # Final value is the mean of the last 10% of the response
    final_value_start_index = int(len(response) * 0.9)
    final_value = np.mean(response[final_value_start_index:])

    # Overshoot
    peak_value = np.max(response)
    overshoot = ((peak_value - final_value) / final_value) * 100 if final_value != 0 else 0

    # Rise Time (10% to 90% of the final value)
    try:
        ten_percent_val = 0.1 * final_value
        ninety_percent_val = 0.9 * final_value

        time_at_10 = time[np.where(response >= ten_percent_val)[0][0]]
        time_at_90 = time[np.where(response >= ninety_percent_val)[0][0]]
        rise_time = time_at_90 - time_at_10
    except IndexError:
        rise_time = np.nan # Not enough data or response didn't cross thresholds

    # Settling Time (time to settle within ±2% of the final value)
    try:
        settling_threshold = 0.02 * final_value
        # Find indices where the response is outside the ±2% band
        unsettled_indices = np.where(np.abs(response - final_value) > settling_threshold)[0]

        if len(unsettled_indices) == 0:
            # If it's always settled, find when it first entered the band
            settled_indices = np.where(np.abs(response - final_value) <= settling_threshold)[0]
            first_settled_index = settled_indices[0] if len(settled_indices) > 0 else 0
            settling_time = time[first_settled_index]
        else:
            # The last time it was outside the band
            last_unsettled_index = unsettled_indices[-1]
            settling_time = time[last_unsettled_index]
    except IndexError:
        settling_time = np.nan

    # Oscillation (sum of absolute error after settling time)
    oscillation = 0
    if not np.isnan(settling_time):
        try:
            settling_index = np.where(time >= settling_time)[0][0]
            oscillation = np.sum(np.abs(response[settling_index:] - final_value))
        except IndexError:
            oscillation = np.nan

    return {
        "Overshoot (%)": overshoot,
        "Rise Time (s)": rise_time,
        "Settling Time (s)": settling_time,
        "Oscillation": oscillation
    }


def classify_step_response(metrics):
    """
    Analyzes response metrics to classify the system's behavior.
    Returns a text description and a color hint.
    """
    if not metrics or any(np.isnan(v) for v in metrics.values()):
        return "Unstable or Incomplete", "red"

    overshoot = metrics.get("Overshoot (%)", 0)
    oscillation = metrics.get("Oscillation", 0)
    rise_time = metrics.get("Rise Time (s)", 1.0)

    if overshoot > 15 or oscillation > 10:
        return "Oscillatory / High Overshoot", "red"
    elif overshoot > 5:
        return "Underdamped (noticeable overshoot)", "orange"
    elif overshoot >= 0:
        if rise_time < 0.08:
             return "Critically Damped (Optimal)", "green"
        else:
             return "Slightly Overdamped (Slow)", "yellow"
    else: # Overshoot is negative
        return "Overdamped (Very Sluggish)", "blue"
