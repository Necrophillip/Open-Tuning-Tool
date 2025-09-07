import numpy as np
import pandas as pd

def find_step_responses(rc_command, time_us, threshold=300, min_step_duration_ms=40, pre_step_flat_ms=10, post_step_flat_ms=100, std_dev_max=50):
    """
    Finds step-like movements in an RC command trace using Pandas.
    """
    if rc_command is None or time_us is None or rc_command.empty:
        return []

    time_s = time_us / 1_000_000
    fs = len(time_us) / (time_s.iloc[-1] - time_s.iloc[0]) if (time_s.iloc[-1] - time_s.iloc[0]) > 0 and len(time_us) > 1 else 2000
    ms_to_indices = lambda ms: int((ms / 1000.0) * fs)

    pre_indices = ms_to_indices(pre_step_flat_ms)
    post_indices = ms_to_indices(post_step_flat_ms) # This is now the duration of the slice *after* the step
    min_duration_indices = ms_to_indices(min_step_duration_ms)

    diffs = rc_command.diff().abs()
    potential_steps = diffs[diffs > threshold].index

    found_steps = []
    last_step_end = -1

    for i in potential_steps:
        # The flat check window is now fixed, e.g., 20ms before and after the step
        flat_check_window = ms_to_indices(20)
        if i <= last_step_end or i < pre_indices or i + flat_check_window >= len(rc_command):
            continue

        # Define the window for checking flatness
        pre_step_segment = rc_command.iloc[i-flat_check_window:i]
        post_step_segment_for_check = rc_command.iloc[i:i+flat_check_window]

        # Define the actual data slice to return, using the new duration parameter
        start_idx = i - pre_indices
        end_idx = i + post_indices # Use the full duration for the slice

        if start_idx < 0 or end_idx >= len(rc_command):
            continue

        # Check for flatness in the small window, but return the large slice
        if pre_step_segment.std() < std_dev_max and post_step_segment_for_check.std() < std_dev_max:
             if end_idx - i > min_duration_indices:
                found_steps.append((start_idx, i, end_idx))
                last_step_end = end_idx

    return found_steps

from .tuning import calculate_response_metrics

def analyze_step_response(time_data, rc_data, gyro_data, dterm_data=None, threshold=200, std_dev_max=50, post_step_duration_ms=100):
    """
    Main analysis function. Converts NumPy arrays to Pandas Series and runs the analysis.
    """
    time_us_pd = pd.Series(time_data)
    rc_data_pd = pd.Series(rc_data)

    steps = find_step_responses(rc_data_pd, time_us_pd, threshold=threshold, std_dev_max=std_dev_max, post_step_flat_ms=post_step_duration_ms)

    if not steps:
        return {
            "error": "No significant steps found.",
            "metrics": {}, "time_slice": np.array([]), "rc_slice": np.array([]),
            "gyro_slice": np.array([]), "dterm_slice": np.array([])
        }

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

    # Convert back to numpy for the metrics function
    metrics = calculate_response_metrics(time_slice_pd.to_numpy(), gyro_slice_pd.to_numpy())

    # The main return should contain the raw slices and the metrics
    # The smoothing will be applied in the GUI
    return {
        "metrics": metrics,
        "time_slice": (time_us_pd.iloc[start:end] / 1_000_000).to_numpy(), # Return time in seconds
        "rc_slice": rc_data_pd.iloc[start:end].to_numpy(),
        "gyro_slice": gyro_data_pd.iloc[start:end].to_numpy(),
        "dterm_slice": dterm_slice_np, # This is already a numpy slice or None
        "error": None
    }

def guess_optimal_params(rc_data):
    """
    Analyzes the rc_data to guess optimal parameters for step detection.
    """
    if rc_data is None or len(rc_data) < 100: # Need enough data to analyze
        return {'threshold': 30, 'std_dev_max': 50} # Return safe defaults

    rc_series = pd.Series(rc_data)
    diffs = rc_series.diff().abs()

    # Guess threshold
    non_zero_diffs = diffs[diffs > 1] # Ignore minor noise
    if not non_zero_diffs.empty:
        # A value that is larger than most noise but smaller than a real step
        guessed_threshold = int(np.percentile(non_zero_diffs, 90))
    else:
        guessed_threshold = 30 # Fallback

    # Clamp threshold to a reasonable range
    guessed_threshold = max(10, min(guessed_threshold, 200))

    # Guess std_dev_max
    # Find quiet periods (where change is minimal)
    quiet_indices = diffs[diffs < 5].index
    if len(quiet_indices) > 50:
        # Calculate std dev in these quiet periods
        noise_level = rc_series[quiet_indices].std()
        # Set tolerance to a multiple of the noise level
        guessed_std_dev = int(noise_level * 4)
    else:
        guessed_std_dev = 50 # Fallback

    # Clamp std_dev_max to a reasonable range
    guessed_std_dev = max(10, min(guessed_std_dev, 200))

    return {'threshold': guessed_threshold, 'std_dev_max': guessed_std_dev}
