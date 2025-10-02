import numpy as np
from fpv_tuner.analysis.utils import apply_smoothing

def get_step_response(df, axis, step_threshold=0.6, duration_s=0.4, min_step_interval_s=0.3, smooth_factor=5):
    """
    Extracts and averages multiple step response sequences from a blackbox log.

    Args:
        df (pd.DataFrame): The blackbox log DataFrame.
        axis (str): 'roll', 'pitch', or 'yaw'.
        step_threshold (float): Normalized change in rcCommand to detect a step.
        duration_s (float): Duration of the response to capture.
        min_step_interval_s (float): Minimum time between detected steps.
        smooth_factor (int): Smoothing level for gyro data.

    Returns:
        A tuple (time_array, averaged_response_array) or (None, None).
    """
    axis_map = {'roll': 0, 'pitch': 1, 'yaw': 2}
    rc_col = f'rcCommand[{axis_map.get(axis, -1)}]'
    gyro_col = f'gyroADC[{axis_map.get(axis, -1)}]'
    time_col = 'time (us)'

    if not all(c in df.columns for c in [rc_col, gyro_col, time_col]):
        return None, None

    # 1. Pre-filter gyro data
    df[gyro_col] = apply_smoothing(df[gyro_col], smooth_factor)

    # 2. Normalize RC command to a range of approx -1 to 1
    rc_min, rc_max = df[rc_col].min(), df[rc_col].max()
    if rc_max == rc_min: return None, None
    rc_normalized = 2 * (df[rc_col] - rc_min) / (rc_max - rc_min) - 1

    # 3. Detect all step transitions
    diff = rc_normalized.diff().abs()
    candidate_indices = df.index[diff > step_threshold]

    if len(candidate_indices) == 0: return None, None

    # Filter candidates to ensure they are spaced apart
    valid_step_indices = []
    last_step_time_us = -np.inf
    min_interval_us = min_step_interval_s * 1_000_000

    for index in candidate_indices:
        current_time_us = df.loc[index, time_col]
        if current_time_us > last_step_time_us + min_interval_us:
            valid_step_indices.append(index)
            last_step_time_us = current_time_us

    if not valid_step_indices: return None, None

    # 4. Extract and normalize each individual response
    all_responses = []
    time_vectors = []

    for start_index in valid_step_indices:
        start_time_us = df.loc[start_index, time_col]
        end_time_us = start_time_us + (duration_s * 1_000_000)

        window_df = df[(df[time_col] >= start_time_us) & (df[time_col] < end_time_us)]
        if len(window_df) < 2: continue

        time_us = window_df[time_col].to_numpy() - start_time_us
        time_s = time_us / 1_000_000

        gyro_window = window_df[gyro_col].to_numpy()
        initial_gyro_val = gyro_window[0]
        gyro_shifted = gyro_window - initial_gyro_val

        rc_window = rc_normalized.loc[window_df.index].to_numpy()
        step_magnitude = rc_window[-1] - rc_window[0]

        if abs(step_magnitude) < 1e-6: continue

        response_normalized = gyro_shifted / step_magnitude

        all_responses.append(response_normalized)
        time_vectors.append(time_s)

    if not all_responses: return None, None

    # 5. Average the responses by taking the median
    max_len = max(len(r) for r in all_responses)
    padded_responses = [np.pad(r, (0, max_len - len(r)), 'edge') for r in all_responses]

    response_stack = np.vstack(padded_responses)
    averaged_response = np.median(response_stack, axis=0)

    # Use the longest time vector as the reference
    time_ref = max(time_vectors, key=len)
    final_time_vector = time_ref[:len(averaged_response)]

    return final_time_vector, averaged_response

def calculate_response_metrics(time, response, setpoint=1.0):
    """
    Calculates key performance metrics from a step response trace.
    """
    if response is None or len(response) < 2: return {}

    final_value_start_index = int(len(response) * 0.9)
    final_value = np.mean(response[final_value_start_index:])
    if np.isclose(final_value, 0): final_value = 1.0 # Avoid division by zero on flat responses

    peak_value = np.max(response)
    overshoot = ((peak_value - final_value) / final_value) * 100 if final_value != 0 else 0

    try:
        ten_percent_val = 0.1 * final_value
        ninety_percent_val = 0.9 * final_value
        time_at_10 = time[np.where(response >= ten_percent_val)[0][0]]
        time_at_90 = time[np.where(response >= ninety_percent_val)[0][0]]
        rise_time = time_at_90 - time_at_10
    except (IndexError, ZeroDivisionError):
        rise_time = np.nan

    try:
        settling_threshold = 0.05 * abs(final_value) # Using 5% threshold
        unsettled_indices = np.where(np.abs(response - final_value) > settling_threshold)[0]
        if len(unsettled_indices) == 0:
            settling_time = time[0]
        else:
            last_unsettled_index = unsettled_indices[-1]
            settling_time = time[last_unsettled_index]
    except (IndexError, ZeroDivisionError):
        settling_time = np.nan

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
        "Oscillation": oscillation,
    }

def classify_step_response(metrics):
    """
    Analyzes response metrics to classify the system's behavior.
    """
    if not metrics or any(np.isnan(v) for v in metrics.values()):
        return "Incomplete Data", "gray"

    overshoot = metrics.get("Overshoot (%)", 0)
    rise_time = metrics.get("Rise Time (s)", 1.0)

    if overshoot > 20: return "Very Oscillatory", "red"
    if overshoot > 10: return "Oscillatory", "orange"
    if rise_time < 0.08: return "Responsive", "green"
    if rise_time > 0.2: return "Sluggish", "blue"
    return "Acceptable", "white"