import pandas as pd
import numpy as np

def find_step_responses(rc_command, time_us, threshold=300, min_step_duration_ms=40, pre_step_flat_ms=10, post_step_flat_ms=100):
    """
    Finds step-like movements in an RC command trace.

    A step is identified by:
    1. A period of relative stability (pre_step_flat_ms).
    2. A very sharp change (the "step").
    3. Another period of relative stability at a new level (post_step_flat_ms).

    Args:
        rc_command (pd.Series): The RC command data for one axis.
        time_us (pd.Series): The time data in microseconds.
        threshold (float): The minimum change in value to be considered a step.
        min_step_duration_ms (int): The minimum duration the signal must be stable after the step.
        pre_step_flat_ms (int): Required stability duration before the step.
        post_step_flat_ms (int): Required stability duration after the step.

    Returns:
        list of tuples: Each tuple contains (start_index, step_index, end_index) for a detected step.
    """
    if rc_command is None or time_us is None or rc_command.empty:
        return []

    # Calculate time delta in ms for index conversion
    time_s = time_us / 1_000_000
    fs = len(time_us) / (time_s.iloc[-1] - time_s.iloc[0])
    ms_to_indices = lambda ms: int((ms / 1000.0) * fs)

    pre_indices = ms_to_indices(pre_step_flat_ms)
    post_indices = ms_to_indices(post_step_flat_ms)
    min_duration_indices = ms_to_indices(min_step_duration_ms)

    # Find sharp changes
    diffs = rc_command.diff().abs()
    potential_steps = diffs[diffs > threshold].index

    found_steps = []
    last_step_end = -1

    for i in potential_steps:
        if i <= last_step_end or i < pre_indices or i + post_indices >= len(rc_command):
            continue

        start_idx = i - pre_indices
        end_idx = i + post_indices

        # The stability check is removed to be more lenient with real-world, noisy logs.
        # The user can now control the window size from the GUI.
        if end_idx - i > min_duration_indices:
            found_steps.append((start_idx, i, end_idx))
            last_step_end = end_idx

    print(f"Found {len(found_steps)} potential step responses.")
    return found_steps


def step_response_metrics(time, input_signal, output_signal):
    """
    Calculates key metrics for a step response.
    Assumes time is a pandas Series with a consistent time step.
    """
    if input_signal.empty or output_signal.empty:
        return {}

    # Initial and final values of the input
    val_i_in = input_signal.iloc[0]
    val_f_in = input_signal.iloc[-1]
    step_amplitude = abs(val_f_in - val_i_in)

    # Initial and final values of the output
    val_i_out = output_signal.iloc[:10].mean() # Average of first few points
    val_f_out = output_signal.iloc[-10:].mean() # Average of last few points

    # Rise Time (10% to 90%)
    try:
        ten_percent_val = val_i_out + 0.1 * (val_f_out - val_i_out)
        ninety_percent_val = val_i_out + 0.9 * (val_f_out - val_i_out)

        time_at_10 = time[output_signal >= ten_percent_val].iloc[0]
        time_at_90 = time[output_signal >= ninety_percent_val].iloc[0]
        rise_time = time_at_90 - time_at_10
    except IndexError:
        rise_time = np.nan

    # Overshoot
    peak_val = output_signal.max()
    overshoot = ((peak_val - val_f_out) / (val_f_out - val_i_out)) * 100 if (val_f_out - val_i_out) != 0 else 0

    # Settling Time (within 2% of final value)
    try:
        settling_threshold = 0.02 * abs(val_f_out - val_i_out)
        outside_bounds = np.where(np.abs(output_signal.values - val_f_out) > settling_threshold)[0]
        last_outside_index = outside_bounds[-1] if len(outside_bounds) > 0 else 0
        settling_time = time.iloc[last_outside_index] - time.iloc[0]
    except (IndexError, ValueError):
        settling_time = np.nan

    return {
        "Step Amplitude": step_amplitude,
        "Rise Time (s)": rise_time,
        "Overshoot (%)": overshoot,
        "Settling Time (s)": settling_time
    }
