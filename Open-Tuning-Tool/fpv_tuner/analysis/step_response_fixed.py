
"""
step_response_fixed.py
Patched utilities to detect "step-like" RC commands and produce realistic, smooth
averaged step responses from RC vs gyro in Betaflight blackbox logs.

Features added/changed compared to the original Jules version:
- Robust stability check (rolling std) before/after candidate step points.
- Smoothing (rolling median) option to reduce quantization "stair-steps".
- Uniform resampling of each response onto a common time vector before averaging
  — avoids jagged averages from misaligned samples.
- Safe guards against empty windows, edge conditions and zero delta_u.
- Optional plotting helper that plots individual traces (alpha) + averaged trace.
- Returns both raw windows and averaged response so you can inspect noise behavior.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Dict, Tuple, Optional

try:
    from scipy.optimize import curve_fit
except Exception:
    curve_fit = None  # curve fitting optional; code will still run without it


# ---------------------------
# Simple models for fitting (optional, require scipy)
# ---------------------------
def first_order_step(t, K, tau):
    return K * (1.0 - np.exp(-t / np.maximum(tau, 1e-9)))


def second_order_step(t, K, wn, zeta):
    wn = np.maximum(wn, 1e-6)
    zeta = np.maximum(zeta, 1e-6)
    if zeta >= 1.0:
        return K * (1.0 - np.exp(-wn * t))
    wd = wn * np.sqrt(1.0 - zeta**2)
    return K * (1.0 - (1.0 / np.sqrt(1.0 - zeta**2)) * np.exp(-zeta * wn * t) *
                np.sin(wd * t + np.arccos(zeta)))


# ---------------------------
# Main improved detection routine
# ---------------------------
def find_step_responses(rc_command: pd.Series,
                        time_us: pd.Series,
                        gyro: Optional[pd.Series] = None,
                        threshold_abs: Optional[float] = None,
                        threshold_rel: float = 0.25,
                        min_step_duration_ms: int = 40,
                        pre_step_flat_ms: int = 10,
                        post_step_flat_ms: int = 120,
                        smoothing_ms: int = 5,
                        resample_dt_ms: Optional[float] = None,
                        stability_std_thresh: float = 2.0,
                        debug: bool = False) -> Dict:
    """
    Detect step-like entries in rc_command and extract corresponding gyro windows.

    Args:
        rc_command: pd.Series of RC command (same length as time_us).
        time_us: pd.Series of timestamps in microseconds.
        gyro: pd.Series of gyro (same length) — if None, results will include windows of None.
        threshold_abs: absolute minimum delta to consider a step (if None, use threshold_rel * max(abs(rc)))
        threshold_rel: fallback relative threshold of the peak RC magnitude
        min_step_duration_ms: minimum time the RC must hold the new value to be considered a deflection run
        pre_step_flat_ms: ms to include before the detected edge (for baseline)
        post_step_flat_ms: ms after the edge to include in the window (can be resized later)
        smoothing_ms: small rolling median applied to RC and gyro to reduce quantization steps
        resample_dt_ms: if provided, resample all windows to this dt (ms); otherwise use native dt
        stability_std_thresh: maximum rolling std (RC units) considered "stable"
        debug: print useful debug information
    Returns:
        dict with keys:
            'windows' : list of dicts { 't_rel': np.array, 'y_norm': np.array, 'delta_u': float, 'idx': int }
            't_avg' : common time vector (s)
            'y_avg' : averaged normalized response (unitless)
            'params' : detection parameters used
    """
    # Convert to numpy/pandas types
    rc = pd.Series(rc_command).reset_index(drop=True)
    t = pd.Series(time_us).reset_index(drop=True)
    if gyro is None:
        gy = None
    else:
        gy = pd.Series(gyro).reset_index(drop=True)

    # Time in seconds
    time_s = t.astype(float).to_numpy() * 1e-6
    if len(time_s) < 2:
        raise ValueError("time_us too short or invalid")

    # nominal dt in seconds and ms
    dt_s = np.median(np.diff(time_s))
    dt_ms = dt_s * 1000.0

    # smoothing (rolling median) to reduce quantization staircase
    smooth_n = max(1, int(round(smoothing_ms / max(dt_ms, 1e-9))))
    if smooth_n > 1:
        rc_smooth = rc.rolling(window=smooth_n, center=True, min_periods=1).median()
        if gy is not None:
            gy_smooth = gy.rolling(window=smooth_n, center=True, min_periods=1).median()
        else:
            gy_smooth = None
    else:
        rc_smooth = rc.copy()
        gy_smooth = gy.copy() if gy is not None else None

    # threshold raw computation
    max_abs_rc = np.nanpercentile(np.abs(rc_smooth), 99)
    if threshold_abs is None:
        threshold_abs = max(1.0, threshold_rel * max_abs_rc)

    # rolling std windows for stability test
    n_pre = max(1, int(round(pre_step_flat_ms / max(dt_ms, 1e-9))))
    n_post = max(1, int(round(post_step_flat_ms / max(dt_ms, 1e-9))))
    roll_std_pre = rc_smooth.rolling(window=n_pre, center=False, min_periods=1).std().fillna(0.0)
    roll_std_post = rc_smooth.rolling(window=n_post, center=False, min_periods=1).std().fillna(0.0)

    # detect candidate rising edges where pre-window is stable and post-window is stable and delta large
    candidates = []
    N = len(rc_smooth)
    for i in range(n_pre, N - n_post - 1):
        std_pre = roll_std_pre.iloc[i - 1]
        std_post = roll_std_post.iloc[i + 1]
        if std_pre <= stability_std_thresh and std_post <= stability_std_thresh:
            mean_pre = rc_smooth.iloc[i - n_pre:i].mean()
            mean_post = rc_smooth.iloc[i:i + n_post].mean()
            delta = mean_post - mean_pre
            if abs(delta) >= threshold_abs:
                # ensure the new value is held at least min_step_duration_ms
                min_len = max(1, int(round(min_step_duration_ms / max(dt_ms, 1e-9))))
                # check that for the next min_len samples the signal stays close to mean_post
                if i + min_len < N:
                    seg = rc_smooth.iloc[i:i + min_len]
                    if seg.std() <= stability_std_thresh:
                        candidates.append(i)

    if debug:
        print(f"Detected {len(candidates)} candidate step indices (threshold_abs={threshold_abs})")

    # Prepare resampling grid
    if resample_dt_ms is None:
        resample_dt_s = dt_s
    else:
        resample_dt_s = resample_dt_ms * 1e-3

    # Build windows
    windows = []
    for idx in candidates:
        i0 = max(0, idx - n_pre)
        i1 = min(N, idx + n_post)
        if i1 - i0 < 3:
            continue  # skip too short windows

        t_win = time_s[i0:i1]
        if gy_smooth is None:
            y_win = None
        else:
            y_win = gy_smooth.iloc[i0:i1].to_numpy(dtype=float)

        # baseline and high value for rc (use short means to reduce noise)
        base = rc_smooth.iloc[max(0, i0):idx].mean()
        high = rc_smooth.iloc[idx:min(N, idx + 3)].mean()
        delta_u = high - base
        if abs(delta_u) < 1e-9:
            continue

        # resample onto common relative time vector if requested (helps averaging)
        t_rel = time_s[i0:i1] - time_s[idx]
        if resample_dt_ms is None:
            # use native samples but align t_rel to start at 0 (may have negative pre)
            t_common = t_rel - t_rel[0]  # start at 0
            if y_win is None:
                y_norm = None
            else:
                y_norm = (y_win - y_win[0]) / delta_u
        else:
            # build relative time grid from -pre to +post using resample_dt_s
            pre_s = pre_step_flat_ms * 1e-3
            post_s = post_step_flat_ms * 1e-3
            t_common = np.arange(-pre_s, post_s, resample_dt_s)
            # absolute time to interpolate at:
            t_abs = np.linspace(time_s[idx] - pre_s, time_s[idx] + post_s - resample_dt_s, len(t_common))
            if y_win is None:
                y_norm = None
            else:
                y_interp = np.interp(t_abs, time_s[i0:i1], y_win, left=np.nan, right=np.nan)
                # normalize with respect to value at t_abs[0]
                if np.isnan(y_interp).all():
                    continue
                y_norm = (y_interp - y_interp[0]) / delta_u

        windows.append({
            "idx": int(idx),
            "t_rel": np.array(t_common),
            "y_norm": np.array(y_norm) if y_norm is not None else None,
            "delta_u": float(delta_u),
            "rc_base": float(base),
            "rc_high": float(high)
        })

    if len(windows) == 0:
        return {"windows": [], "t_avg": None, "y_avg": None, "params": {
            "threshold_abs": threshold_abs,
            "threshold_rel": threshold_rel,
            "n_candidates": len(candidates)
        }}

    # Build average by stacking interpolated arrays with uniform length
    # Find minimum common length if resample_dt_ms is None; else all windows have same length
    lengths = [len(w["t_rel"]) for w in windows if w["y_norm"] is not None]
    if len(lengths) == 0:
        return {"windows": windows, "t_avg": None, "y_avg": None, "params": {
            "threshold_abs": threshold_abs,
            "threshold_rel": threshold_rel,
            "n_candidates": len(candidates)
        }}

    if resample_dt_ms is None:
        L = min(lengths)
        t_avg = windows[0]["t_rel"][:L]
        Y = np.vstack([w["y_norm"][:L] for w in windows])
    else:
        # all windows same length
        L = lengths[0]
        t_avg = windows[0]["t_rel"]
        Y = np.vstack([w["y_norm"] for w in windows if w["y_norm"] is not None])

    y_avg = np.nanmean(Y, axis=0)

    return {
        "windows": windows,
        "t_avg": t_avg,
        "y_avg": y_avg,
        "params": {
            "threshold_abs": threshold_abs,
            "threshold_rel": threshold_rel,
            "smoothing_ms": smoothing_ms,
            "resample_dt_ms": resample_dt_ms,
            "n_windows": len(windows)
        }
    }


# ---------------------------
# Plot helper
# ---------------------------
def plot_step_windows(result: Dict, axis_name: str = "Axis", show_individuals: bool = True):
    """
    Plot the extracted windows and the averaged response.
    """
    if result["t_avg"] is None or result["y_avg"] is None:
        print("No windows to plot")
        return

    t_ms = np.array(result["t_avg"]) * 1000.0
    y = result["y_avg"]

    plt.figure(figsize=(9, 5))
    if show_individuals:
        for w in result["windows"]:
            if w["y_norm"] is None:
                continue
            # align length
            arr = w["y_norm"][:len(t_ms)]
            plt.plot(t_ms, arr, linewidth=0.8, alpha=0.35, zorder=1)

    plt.plot(t_ms, y, linewidth=2.2, zorder=3, label="Average (normalized)")
    plt.axvline(0.0, color="k", linewidth=0.6, alpha=0.6)
    plt.xlabel("Time desde el escalón (ms)")
    plt.ylabel(f"{axis_name} salida normalizada")
    plt.title(f"{axis_name} - Step-like response (entry to high deflection)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


# ---------------------------
# Optional: fit models if scipy available
# ---------------------------
def fit_models_to_avg(t, y):
    if curve_fit is None:
        raise RuntimeError("scipy.optimize.curve_fit required for model fitting")

    res = {}
    try:
        popt1, _ = curve_fit(first_order_step, t, y, p0=[1.0, 0.02], bounds=([0.0, 1e-4], [10.0, 1.0]))
        res["first_order"] = {"K": float(popt1[0]), "tau": float(popt1[1]), "y_fit": first_order_step(t, *popt1)}
    except Exception:
        res["first_order"] = None

    try:
        popt2, _ = curve_fit(second_order_step, t, y, p0=[1.0, 200.0, 0.4], bounds=([0.0, 1.0, 0.01], [10.0, 5000.0, 0.99]))
        res["second_order"] = {"K": float(popt2[0]), "wn": float(popt2[1]), "zeta": float(popt2[2]), "y_fit": second_order_step(t, *popt2)}
    except Exception:
        res["second_order"] = None

    return res
