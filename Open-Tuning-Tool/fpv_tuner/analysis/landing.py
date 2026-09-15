from __future__ import annotations

import numpy as np
import pandas as pd

def measure_landing_bounce(df: pd.DataFrame) -> dict | None:
    """
    Detects a landing event (throttle dropping to ~zero at the end of a flight segment)
    and measures the subsequent bounce (gyro variation).

    Returns:
        dict: {"bounce_rms": float, "bounce_max": float} or None if no valid landing found.
    """
    throttle_col = next((c for c in df.columns if "rcCommand[3]" in c), None)
    if not throttle_col:
        # Fallback if it's named differently
        throttle_col = next((c for c in df.columns if "throttle" in c.lower() and "rc" in c.lower()), None)
    
    time_col = next((c for c in df.columns if "time" in c.lower() and "us" in c.lower()), None)
    
    if not throttle_col or not time_col:
        return None

    gyro_cols = [c for c in df.columns if c.startswith("gyroADC[")]
    if not gyro_cols:
        return None

    # We look for the final segment where throttle goes from active (>1100) to idle (< 1050)
    thr = df[throttle_col].values.astype(float)
    t = df[time_col].values.astype(float)

    # Typical idle is 1000. Let's say < 1050 is "throttle cut".
    # We want to find the LAST transition from > 1100 to < 1050.
    active_mask = thr > 1100
    idle_mask = thr < 1050

    # If never active or never idle, no clear landing event
    if not np.any(active_mask) or not np.any(idle_mask):
        return None

    # Find the last index where it was active
    last_active_idx = np.where(active_mask)[0][-1]

    # Find the first idle index AFTER the last active index
    subsequent_idles = np.where(idle_mask[last_active_idx:])[0]
    if len(subsequent_idles) == 0:
        return None # Never went idle after being active at the end

    landing_start_idx = last_active_idx + subsequent_idles[0]

    # Look at a window of time after the throttle cut (e.g., 0.5 to 1.5 seconds)
    # We measure time in microseconds usually.
    landing_time = t[landing_start_idx]
    
    # 2 seconds max window
    window_mask = (t >= landing_time) & (t <= landing_time + 2_000_000)
    window_indices = np.where(window_mask)[0]
    
    if len(window_indices) < 10:
        return None

    bounce_rms_vals = []
    bounce_max_vals = []
    
    for col in gyro_cols:
        gyro_window = df[col].values[window_indices].astype(float)
        if len(gyro_window) > 0:
            rms = np.sqrt(np.mean(gyro_window**2))
            max_val = np.max(np.abs(gyro_window))
            bounce_rms_vals.append(rms)
            bounce_max_vals.append(max_val)

    if not bounce_rms_vals:
        return None

    return {
        "bounce_rms": float(max(bounce_rms_vals)),
        "bounce_max": float(max(bounce_max_vals))
    }
