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

        pre_step_segment = rc_command.iloc[start_idx:i]
        post_step_segment = rc_command.iloc[i:end_idx]

        # Check for stability before and after the step
        if pre_step_segment.std() < 50 and post_step_segment.std() < 50:
            # Check if the step holds for the minimum duration
            if end_idx - i > min_duration_indices:
                found_steps.append((start_idx, i, end_idx))
                last_step_end = end_idx

    print(f"Found {len(found_steps)} potential step responses.")
    return found_steps
