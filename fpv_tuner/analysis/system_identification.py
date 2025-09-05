import numpy as np
import pandas as pd

def find_step_responses(rc_command, time_us, threshold=300, min_step_duration_ms=40, pre_step_flat_ms=10, post_step_flat_ms=100, std_dev_max=50):
    """
    Finds step-like movements in an RC command trace using Pandas.
    This is a more direct adaptation of the user's provided script.
    """
    if rc_command is None or time_us is None or rc_command.empty:
        return []

    time_s = time_us / 1_000_000
    if (time_s.iloc[-1] - time_s.iloc[0]) > 0 and len(time_us) > 1:
        fs = len(time_us) / (time_s.iloc[-1] - time_s.iloc[0])
    else:
        fs = 2000

    ms_to_indices = lambda ms: int((ms / 1000.0) * fs)

    pre_indices = ms_to_indices(pre_step_flat_ms)
    post_indices = ms_to_indices(post_step_flat_ms)
    min_duration_indices = ms_to_indices(min_step_duration_ms)

    diffs = rc_command.diff().abs()
    potential_steps = diffs[diffs > threshold].index

    found_steps = []
    last_step_end = -1

    for i in potential_steps:
        if i <= last_step_end or i < pre_indices or i + post_indices >= len(rc_command):
            continue

        start_idx = i - pre_indices
        end_idx = i + post_indices

        pre_step_segment = rc_command.iloc[start_idx:i]
        post_step_segment = rc_command.iloc[i:end_idx]

        if pre_step_segment.std() < std_dev_max and post_step_segment.std() < std_dev_max:
            if end_idx - i > min_duration_indices:
                found_steps.append((start_idx, i, end_idx))
                last_step_end = end_idx

    return found_steps

def step_response_metrics(time, input_signal, output_signal):
    """
    Calculates key metrics for a step response using Pandas Series.
    """
    val_i_in = input_signal.iloc[0]
    val_f_in = input_signal.iloc[-1]
    step_amplitude = abs(val_f_in - val_i_in)

    val_i_out = output_signal.iloc[:10].mean()
    val_f_out = output_signal.iloc[-10:].mean()

    try:
        ten_percent_val = val_i_out + 0.1 * (val_f_out - val_i_out)
        ninety_percent_val = val_i_out + 0.9 * (val_f_out - val_i_out)
        time_at_10 = time[output_signal >= ten_percent_val].iloc[0]
        time_at_90 = time[output_signal >= ninety_percent_val].iloc[0]
        rise_time = time_at_90 - time_at_10
    except IndexError:
        rise_time = np.nan

    peak_val = output_signal.max()
    overshoot = ((peak_val - val_f_out) / (val_f_out - val_i_out)) * 100 if (val_f_out - val_i_out) != 0 else 0

    try:
        settling_threshold = 0.02 * abs(val_f_out - val_i_out)
        outside_bounds = np.where(np.abs(output_signal.to_numpy() - val_f_out) > settling_threshold)[0]
        last_outside_index = outside_bounds[-1] if len(outside_bounds) > 0 else 0
        settling_time = time.iloc[last_outside_index] - time.iloc[0]
    except IndexError:
        settling_time = np.nan

    return {
        "Step Amplitude": step_amplitude,
        "Rise Time (s)": rise_time,
        "Overshoot (%)": overshoot,
        "Settling Time (s)": settling_time
    }

def analyze_step_response(time_data, rc_data, gyro_data, dterm_data=None, threshold=200, std_dev_max=50):
    """
    Main analysis function. Converts NumPy arrays to Pandas Series and runs the analysis.
    """
    time_us_pd = pd.Series(time_data)
    rc_data_pd = pd.Series(rc_data)

    steps = find_step_responses(rc_data_pd, time_us_pd, threshold=threshold, std_dev_max=std_dev_max)

    if not steps:
        return {"error": "No significant steps found."}

    start, step_idx, end = steps[0]

    time_slice_pd = time_us_pd.iloc[start:end].copy() / 1_000_000
    time_slice_pd.reset_index(drop=True, inplace=True)

    rc_slice_pd = rc_data_pd.iloc[start:end].copy().reset_index(drop=True)

    gyro_data_pd = pd.Series(gyro_data)
    gyro_slice_pd = gyro_data_pd.iloc[start:end].copy().reset_index(drop=True)

    dterm_slice_np = None
    if dterm_data is not None:
        dterm_data_pd = pd.Series(dterm_data)
        dterm_slice_np = dterm_data_pd.iloc[start:end].copy().to_numpy()

    metrics = step_response_metrics(time_slice_pd, rc_slice_pd, gyro_slice_pd)

    return {
        "metrics": metrics,
        "time_slice": time_slice_pd.to_numpy(),
        "rc_slice": rc_slice_pd.to_numpy(),
        "gyro_slice": gyro_slice_pd.to_numpy(),
        "dterm_slice": dterm_slice_np,
        "error": None
    }
