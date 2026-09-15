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
from fpv_tuner.analysis.harmonics import compute_motor_harmonics

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


def compute_step_response_summary(df: pd.DataFrame, axis_name: str, pids: dict = None):
    """
    Compute a normalized step response for one axis.

    Returns ``{"t", "response", "overshoot_pct", "rise_time_s", "settling_time_s"}``
    or None when the axis cannot be analysed.
    """
    idx = AXES.index(axis_name)
    time_col = _find_time_col(df)
    rc_col = f"rcCommand[{idx}]"
    gyro_col = f"gyroADC[{idx}]"
    p_col = f"axisP[{idx}]"
    
    if time_col not in df.columns or gyro_col not in df.columns:
        return None

    # Reconstruct setpoint if rcCommand is missing but we have axisP and P gain
    setpoint = None
    if rc_col in df.columns:
        setpoint = df[rc_col].to_numpy()
    elif p_col in df.columns and pids is not None:
        p_gain = float(pids.get(f"p_{axis_name}") or 0.0)
        if p_gain > 0:
            # axisP = P_gain * (Setpoint - Gyro)  =>  Setpoint = (axisP / P_gain) + Gyro
            # Note: This is a simplification but works as a rough proxy for step response
            axis_p_scaled = df[p_col].astype(float).to_numpy() / p_gain
            gyro = df[gyro_col].astype(float).to_numpy()
            setpoint = axis_p_scaled + gyro
            
    if setpoint is None:
        return None

    est_fs = _estimate_loop_hz(df, time_col)
    
    motor_cols = [c for c in df.columns if c.startswith("motor[") and "]" in c]
    motor_signals = [df[c].to_numpy() for c in motor_cols] if motor_cols else None
    
    try:
        analysis = analyze_step_response(
            df[time_col].to_numpy(dtype=np.int64),
            setpoint,
            df[gyro_col].to_numpy(),
            pid_loop_hz=est_fs,
            plot=False,
            return_fit_curve=True,
            motor_signals=motor_signals,
        )
    except Exception:
        return None

    if analysis is None or "error" in analysis:
        return None

    metrics = analysis.get("metrics", {})
    t_seg = analysis.get("t_segment")
    y_seg = analysis.get("y_segment")
    u_seg = analysis.get("u_segment")
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
    
    u0 = np.mean(u_seg[:max(1, int(0.05 * len(u_seg)))]) if u_seg is not None else 0
    setpoint = (np.asarray(u_seg, dtype=float) - u0) / step_amp if u_seg is not None else np.ones_like(t)

    overshoot = max(0.0, float(np.max(response) - 1.0)) * 100.0
    zeta = metrics.get("zeta")
    is_first_order = metrics.get("model") == "first-order"
    
    if is_first_order:
        system_type = "Overdamped"
    elif zeta is not None:
        system_type = "Underdamped" if zeta < 0.99 else "Overdamped"
    else:
        system_type = "Unknown"

    return {
        "t": t,
        "response": response,
        "setpoint": setpoint,
        "type": system_type,
        "overshoot_pct": overshoot,
        "rise_time_ms": (metrics.get("rise_time_s") or 0.0) * 1000.0,
        "delay_ms": (metrics.get("time_delay_s") or 0.0) * 1000.0,
    }


def compute_noise_heatmap(df: pd.DataFrame, axis_name: str, n_throttle_bins: int = 80,
                          n_freq_bins: int = 256, col_prefix: str = "gyroADC", motor_poles: int = 14):
    """
    Compute a throttle-vs-noise heatmap for a given signal prefix (gyroADC, axisD, etc).

    Returns ``{"throttle", "freq", "heatmap"}`` or None.
    """
    idx = AXES.index(axis_name)
    time_col = _find_time_col(df)
    noise_col = f"{col_prefix}[{idx}]"
    if noise_col not in df.columns:
        alt_prefix = "dTerm" if col_prefix == "axisD" else "axisD"
        noise_col = f"{alt_prefix}[{idx}]"
    throttle_col = next((c for c in df.columns if "rccommand" in c.lower() and "3" in c), None)
    if throttle_col is None:
        throttle_col = next((c for c in df.columns if c == "motor[0]"), None)

    if not all(c in df.columns for c in (time_col, noise_col, throttle_col)):
        return None

    raw = df[throttle_col].astype(float)
    if raw.max() > 1000:
        throttle = ((raw - 1000) / 1000.0 * 100.0).clip(0, 100)
    else:
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
        
    result = {"throttle": tc, "freq": fb, "heatmap": hm}
    
    # Overlay Harmonics calculation
    harmonics_df = compute_motor_harmonics(df, motor_poles, time_col)
    if harmonics_df is not None:
        # Group harmonics into the exact same throttle bins
        import pandas as pd
        valid_idx = throttle.notna() & harmonics_df['h1_hz'].notna()
        t_clean = throttle[valid_idx].values
        
        if len(t_clean) > 0:
            bins = np.linspace(0.0, 100.0, len(tc) + 1)
            bin_indices = np.digitize(t_clean, bins) - 1
            bin_indices = np.clip(bin_indices, 0, len(tc) - 1)
            
            df_h = pd.DataFrame({'bin': bin_indices})
            for h_col, key in [('h1_hz', 'h1'), ('h2_hz', 'h2'), ('h3_hz', 'h3')]:
                df_h[key] = harmonics_df[h_col][valid_idx].values
                
            mean_h = df_h.groupby('bin').mean()
            
            for key in ['h1', 'h2', 'h3']:
                binned_h = np.full(len(tc), np.nan)
                for b_idx in mean_h.index:
                    binned_h[b_idx] = mean_h.at[b_idx, key]
                
                # Interpolate missing bins
                mask = np.isnan(binned_h)
                if not mask.all():
                    binned_h[mask] = np.interp(np.flatnonzero(mask), np.flatnonzero(~mask), binned_h[~mask])
                    
                result[key] = binned_h

    return result
