"""
Summary analysis — step response + noise heatmaps for the review page.

Produces compact, plottable results per axis (roll/pitch/yaw) that the
Export/Review page renders before the user applies changes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fpv_tuner.analysis.step_response import analyze_step_response
from fpv_tuner.analysis.noise import calculate_throttle_noise_heatmap

AXES = ("roll", "pitch", "yaw")


def _find_time_col(df: pd.DataFrame):
    return next((c for c in df.columns if "time" in c.lower() and "us" in c.lower()), None)


def _estimate_loop_hz(df: pd.DataFrame, time_col: str) -> int:
    try:
        dt = np.diff(df[time_col].to_numpy(dtype=float))
        dt = dt[dt > 0]
        median_dt = np.median(dt)
        return int(round(1e6 / median_dt)) if median_dt > 0 else 4000
    except Exception:
        return 4000


def compute_step_response_summary(df: pd.DataFrame, axis_name: str):
    """
    Compute a normalized step response for one axis.

    Returns ``{"t", "response", "overshoot_pct", "rise_time_s", "settling_time_s"}``
    or None when the axis cannot be analysed.
    """
    idx = AXES.index(axis_name)
    time_col = _find_time_col(df)
    rc_col = f"rcCommand[{idx}]"
    gyro_col = f"gyroADC[{idx}]"
    if not all(c in df.columns for c in (time_col, rc_col, gyro_col)):
        return None

    est_fs = _estimate_loop_hz(df, time_col)
    try:
        analysis = analyze_step_response(
            df[time_col].to_numpy(dtype=np.int64),
            df[rc_col].to_numpy(),
            df[gyro_col].to_numpy(),
            pid_loop_hz=est_fs,
            plot=False,
            return_fit_curve=True,
        )
    except Exception:
        return None

    if analysis is None or "error" in analysis:
        return None

    metrics = analysis.get("metrics", {})
    t_seg = analysis.get("t_segment")
    y_seg = analysis.get("y_segment")
    if t_seg is None or y_seg is None or len(t_seg) == 0:
        return None

    step_amp = metrics.get("step_input_amplitude", 1.0)
    y0 = metrics.get("y0", 0.0)
    if step_amp is None or np.isclose(step_amp, 0):
        step_amp = 1.0
        y0 = float(np.mean(np.asarray(y_seg)[:max(1, 5)]))

    t = np.asarray(t_seg, dtype=float)
    t = t - t[0]
    response = (np.asarray(y_seg, dtype=float) - y0) / step_amp
    response = np.nan_to_num(response, nan=0.0, posinf=0.0, neginf=0.0)

    return {
        "t": t,
        "response": response,
        "overshoot_pct": float(metrics.get("overshoot_pct", 0.0) or 0.0),
        "rise_time_s": metrics.get("rise_time_s"),
        "settling_time_s": metrics.get("settling_time_s"),
    }


def compute_noise_heatmap(df: pd.DataFrame, axis_name: str, n_throttle_bins: int = 24,
                          n_freq_bins: int = 64):
    """
    Compute a throttle-vs-noise heatmap for one gyro axis.

    Returns ``{"throttle", "freq", "heatmap"}`` or None.
    """
    idx = AXES.index(axis_name)
    time_col = _find_time_col(df)
    noise_col = f"gyroADC[{idx}]"
    throttle_col = next((c for c in df.columns if "rccommand" in c.lower() and "3" in c), None)
    if throttle_col is None:
        throttle_col = next((c for c in df.columns if c == "motor[0]"), None)

    if not all(c in df.columns for c in (time_col, noise_col, throttle_col)):
        return None

    raw = df[throttle_col].astype(float)
    mn, mx = raw.min(), raw.max()
    if mx > mn:
        throttle = (raw - mn) / (mx - mn) * 100.0
    else:
        throttle = pd.Series(np.full(len(raw), 50.0), index=raw.index)

    nperseg = min(256, max(64, len(df) // 4))
    tc, fb, hm = calculate_throttle_noise_heatmap(
        df[noise_col], throttle, df[time_col],
        n_throttle_bins=n_throttle_bins, n_freq_bins=n_freq_bins, nperseg=nperseg,
    )
    if tc is None or hm is None:
        return None
    return {"throttle": tc, "freq": fb, "heatmap": hm}
