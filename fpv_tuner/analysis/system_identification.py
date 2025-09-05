import numpy as np

def find_step_responses(rc_command, time_us, threshold=300, min_step_duration_ms=40, pre_step_flat_ms=10, post_step_flat_ms=100):
    """
    Finds step-like movements in an RC command trace using NumPy.
    """
    if rc_command is None or time_us is None or len(rc_command) == 0:
        return []

    time_s = time_us / 1_000_000
    # Handle case where time_s might be empty or have a single point
    if (time_s[-1] - time_s[0]) > 0 and len(time_us) > 1:
        fs = len(time_us) / (time_s[-1] - time_s[0])
    else:
        fs = 2000 # Default fallback sampling frequency

    ms_to_indices = lambda ms: int((ms / 1000.0) * fs)

    pre_indices = ms_to_indices(pre_step_flat_ms)
    post_indices = ms_to_indices(post_step_flat_ms)
    min_duration_indices = ms_to_indices(min_step_duration_ms)

    # np.diff is equivalent to pandas .diff()
    diffs = np.abs(np.diff(rc_command, prepend=rc_command[0]))
    potential_steps = np.where(diffs > threshold)[0]

    found_steps = []
    last_step_end = -1

    for i in potential_steps:
        if i <= last_step_end or i < pre_indices or i + post_indices >= len(rc_command):
            continue

        start_idx = i - pre_indices
        end_idx = i + post_indices

        pre_step_segment = rc_command[start_idx:i]
        post_step_segment = rc_command[i:end_idx]

        # np.std is equivalent to pandas .std()
        if np.std(pre_step_segment) < 50 and np.std(post_step_segment) < 50:
            if end_idx - i > min_duration_indices:
                found_steps.append((start_idx, i, end_idx))
                last_step_end = end_idx

    return found_steps

def step_response_metrics(time, input_signal, output_signal):
    """
    Calculates key metrics for a step response using NumPy.
    """
    # Initial and final values of the input
    val_i_in = input_signal[0]
    val_f_in = input_signal[-1]
    step_amplitude = abs(val_f_in - val_i_in)

    # Initial and final values of the output
    val_i_out = np.mean(output_signal[:10])
    val_f_out = np.mean(output_signal[-10:])

    # Rise Time (10% to 90%)
    try:
        ten_percent_val = val_i_out + 0.1 * (val_f_out - val_i_out)
        ninety_percent_val = val_i_out + 0.9 * (val_f_out - val_i_out)

        # np.where returns a tuple of arrays, we need the first element
        time_at_10_indices = np.where(output_signal >= ten_percent_val)[0]
        time_at_90_indices = np.where(output_signal >= ninety_percent_val)[0]

        if len(time_at_10_indices) == 0 or len(time_at_90_indices) == 0:
             raise IndexError("Could not find 10% or 90% point.")

        time_at_10 = time[time_at_10_indices[0]]
        time_at_90 = time[time_at_90_indices[0]]
        rise_time = time_at_90 - time_at_10
    except IndexError:
        rise_time = np.nan

    # Overshoot
    peak_val = np.max(output_signal)
    overshoot = ((peak_val - val_f_out) / (val_f_out - val_i_out)) * 100 if (val_f_out - val_i_out) != 0 else 0

    # Settling Time (within 2% of final value)
    try:
        settling_threshold = 0.02 * abs(val_f_out - val_i_out)
        outside_bounds = np.where(np.abs(output_signal - val_f_out) > settling_threshold)[0]
        last_outside_index = outside_bounds[-1] if len(outside_bounds) > 0 else 0
        settling_time = time[last_outside_index] - time[0]
    except IndexError:
        settling_time = np.nan

    return {
        "Step Amplitude": step_amplitude,
        "Rise Time (s)": rise_time,
        "Overshoot (%)": overshoot,
        "Settling Time (s)": settling_time
    }

def analyze_step_response(time_data, rc_data, gyro_data, dterm_data=None, threshold=200):
    """
    Main analysis function to be called from the GUI.
    Finds the most significant step and returns its data and metrics.
    """
    # find_step_responses expects time in us
    steps = find_step_responses(rc_data, time_data, threshold=threshold)

    if not steps:
        return {"error": "No significant steps found."}

    # For now, analyze the first step found
    start, step_idx, end = steps[0]

    # Slice the data for the found step
    time_slice = time_data[start:end].copy() / 1_000_000 # Convert to seconds
    time_slice -= time_slice[0] # Start time from 0 for the plot

    rc_slice = rc_data[start:end].copy()
    gyro_slice = gyro_data[start:end].copy()

    dterm_slice = None
    if dterm_data is not None:
        dterm_slice = dterm_data[start:end].copy()

    # Calculate metrics on the sliced data
    metrics = step_response_metrics(time_slice, rc_slice, gyro_slice)

    return {
        "metrics": metrics,
        "time_slice": time_slice,
        "rc_slice": rc_slice,
        "gyro_slice": gyro_slice,
        "dterm_slice": dterm_slice,
        "error": None
    }
