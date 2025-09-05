import re
import numpy as np
from scipy.signal import lti, step

def parse_dump(file_path):
    """
    Parses a Betaflight dump file to extract a comprehensive set of tuning parameters.
    It prioritizes settings under the active profile but also reads global settings.
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
    active_profile_id = -1
    profile_settings = {}
    global_settings = {}

    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        # Find the active profile ID first
        for line in lines:
            if line.strip().startswith('profile '):
                active_profile_id = int(line.strip().split(' ')[1])
                break
        if active_profile_id == -1: active_profile_id = 0 # Default to 0 if not found

        # Parse the entire file, separating global and profile-specific settings
        in_profile_block = False
        current_profile_id = -1
        for line in lines:
            line = line.strip()

            # Check for profile block start
            if line.startswith('# profile '):
                in_profile_block = True
                current_profile_id = int(line.split(' ')[2])
                continue

            # Check for profile block end
            if in_profile_block and (line.startswith('#') or not line):
                in_profile_block = False
                current_profile_id = -1
                continue

            # Match any 'set' command
            match = re.match(r'set\s+([\w_]+)\s+=\s+([\w\d.-]+)', line)
            if not match:
                continue

            key, value = match.group(1), match.group(2)

            if key not in TARGET_KEYS:
                continue

            # Try to convert value to a number, otherwise keep as string
            try:
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value)
            except ValueError:
                pass # Keep as string (e.g., for filter types like 'PT1')

            if in_profile_block and current_profile_id == active_profile_id:
                profile_settings[key] = value
            else:
                global_settings[key] = value

        # Merge settings: profile settings override global settings
        settings = global_settings.copy()
        settings.update(profile_settings)

    except FileNotFoundError:
        return None, f"Dump file not found at '{file_path}'"
    except Exception as e:
        return None, f"An error occurred while parsing: {e}"

    if not settings:
        return None, "Could not find any relevant tuning settings in the dump file."

    return settings, None


# A basic framework for parameter validation. This can be expanded significantly.
# Ranges are conservative and may not apply to all quad sizes or firmware versions.
SAFE_RANGES = {
    'p_roll': (20, 150),
    'i_roll': (20, 150),
    'd_roll': (10, 100),
    'f_roll': (0, 300),
    'p_pitch': (20, 150),
    'i_pitch': (20, 150),
    'd_pitch': (10, 100),
    'f_pitch': (0, 300),
    'p_yaw': (20, 150),
    'i_yaw': (20, 150),
    'd_yaw': (0, 50),
    'f_yaw': (0, 300),
    'dterm_lpf1_static_hz': (20, 400),
    'gyro_lpf1_static_hz': (50, 800),
}

def validate_settings(settings):
    """
    Validates a dictionary of settings against the SAFE_RANGES.
    Returns a list of warning strings.
    """
    warnings = []
    for key, (min_val, max_val) in SAFE_RANGES.items():
        if key in settings:
            value = settings[key]
            if not isinstance(value, (int, float)):
                continue # Cannot validate non-numeric types like 'PT1'
            if not min_val <= value <= max_val:
                warnings.append(
                    f"Warning: '{key}' value of {value} is outside the "
                    f"recommended safe range of ({min_val} - {max_val})."
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


def _calculate_fitness(metrics):
    """
    Calculates a fitness score from a metrics dictionary. Lower is better.
    """
    if not metrics:
        return float('inf')

    # Weights for each metric component. Tune these to change tuning preference.
    WEIGHT_OVERSHOOT = 2.0
    WEIGHT_SETTLING = 1.0
    WEIGHT_RISE_TIME = 0.5
    WEIGHT_OSCILLATION = 1.5

    # Penalize heavily for instability (NaN values or extreme overshoot)
    if np.isnan(metrics.get("Settling Time (s)", 0)) or metrics.get("Overshoot (%)", 100) > 100:
        return float('inf')

    score = (
        metrics.get("Overshoot (%)", 50) * WEIGHT_OVERSHOOT +
        metrics.get("Settling Time (s)", 1) * 100 * WEIGHT_SETTLING + # Scale time to be competitive
        metrics.get("Rise Time (s)", 1) * 100 * WEIGHT_RISE_TIME +
        metrics.get("Oscillation", 100) * WEIGHT_OSCILLATION
    )
    return score


def find_optimal_tune(initial_pids, iterations=50):
    """
    Uses a simple hill-climbing algorithm to find a better PID tune.
    """
    best_pids = initial_pids.copy()

    # Run a baseline simulation to get the initial fitness score
    time, response, _ = simulate_step_response(best_pids, noise_level=0.05) # Use a standard noise level for fitness
    if time is None:
        return initial_pids # Cannot simulate, return original

    metrics = calculate_response_metrics(time, response)
    best_fitness = _calculate_fitness(metrics)

    for _ in range(iterations):
        # Create a new candidate by slightly modifying the current best
        candidate_pids = best_pids.copy()

        # Randomly choose to adjust P or D gain for roll or pitch
        param_to_tweak = np.random.choice(['p_roll', 'd_roll', 'p_pitch', 'd_pitch'])
        # Adjust by a random amount between -3 and +3
        adjustment = np.random.randint(-3, 4)

        candidate_pids[param_to_tweak] += adjustment

        # Validate the new candidate against safe ranges
        warnings = validate_settings(candidate_pids)
        if warnings:
            continue # Skip this candidate if it's outside safe ranges

        # Simulate and calculate fitness for the candidate
        time, response, _ = simulate_step_response(candidate_pids, noise_level=0.05)
        if time is None:
            continue

        metrics = calculate_response_metrics(time, response)
        candidate_fitness = _calculate_fitness(metrics)

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


def simulate_step_response(pids, inertia=0.005, duration=0.2, time_steps=500, noise_level=0.0,
                         disturbance_magnitude=0.0, disturbance_time=0.0):
    """
    Simulates the step response of a PID controller using a discrete-time loop.
    This allows for the injection of noise and other non-linearities.

    Args:
        pids (dict): A dictionary containing keys like 'p_roll', 'd_roll'.
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

    if 'p_roll' in pids:
        Kp = pids.get('p_roll', 0) * P_SCALE
        Ki = pids.get('i_roll', 0) * I_SCALE
        Kd = pids.get('d_roll', 0) * D_SCALE
    elif 'p_pitch' in pids:
        Kp = pids.get('p_pitch', 0) * P_SCALE
        Ki = pids.get('i_pitch', 0) * I_SCALE
        Kd = pids.get('d_pitch', 0) * D_SCALE
    else:
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
    d_term_trace = np.zeros(time_steps)

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
        d_term_trace[i] = d_term # Store the final D-term value after filtering

        # Update state for next iteration
        previous_error = error

    return t, response, d_term_trace


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
