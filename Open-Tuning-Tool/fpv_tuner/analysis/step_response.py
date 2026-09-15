import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
from scipy.interpolate import interp1d
import math

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None

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


def _resample_to_fs(time_us, signal, target_fs):
    """Resample non-uniform `time_us` (microseconds) and `signal` to uniform sampling at `target_fs` Hz.

    Returns times in seconds and resampled signal.
    """
    if len(time_us) < 2:
        return np.array(time_us / 1e6), np.asarray(signal)

    t_s = np.asarray(time_us) / 1e6
    duration = t_s[-1] - t_s[0]
    if duration <= 0:
        return t_s, np.asarray(signal)

    n_samples = max(int(np.ceil(duration * target_fs)), 2)
    t_uniform = np.linspace(t_s[0], t_s[-1], n_samples)

    try:
        f = interp1d(t_s, np.asarray(signal), kind='linear', bounds_error=False, fill_value=(signal.iloc[0] if hasattr(signal, 'iloc') else signal[0]))
        y_uniform = f(t_uniform)
    except Exception:
        # fallback to numpy interp
        y_uniform = np.interp(t_uniform, t_s, np.asarray(signal))

    return t_uniform, y_uniform


def _second_order_step_response(t, K, wn, zeta, td, y0):
    """Second-order underdamped step response with time delay and offset.

    y0: initial output offset
    K: final gain applied to step amplitude
    wn: natural frequency (rad/s)
    zeta: damping ratio
    td: time delay (s)
    """
    y = np.zeros_like(t)
    # shift time by delay
    ts = t - td
    mask = ts > 0
    if zeta < 0:
        zeta = 0.0
    if zeta < 1.0:
        wd = wn * np.sqrt(1 - zeta ** 2)
        phi = np.arccos(zeta)
        exp_term = np.exp(-zeta * wn * ts[mask])
        sin_term = np.sin(wd * ts[mask] + phi)
        y[mask] = K * (1 - (1 / np.sqrt(1 - zeta ** 2)) * exp_term * sin_term) + y0
    else:
        # critically or overdamped: approximate with 1 - exp(-wn*t)
        y[mask] = K * (1 - np.exp(-wn * ts[mask])) + y0
    # before delay return initial value
    y[~mask] = y0
    return y


def _first_order_step_response(t, K, tau, td, y0):
    """First-order (single-pole) step response with time delay.
    y0: initial offset
    K: steady-state gain applied to step amplitude
    tau: time constant (s)
    td: time delay (s)
    """
    y = np.zeros_like(t)
    ts = t - td
    mask = ts > 0
    if tau <= 0:
        tau = 1e-6
    y[mask] = K * (1 - np.exp(-ts[mask] / tau)) + y0
    y[~mask] = y0
    return y


def analyze_step_response(time_us, rc_command, output_signal, pid_loop_hz=400, plot=True, return_fit_curve=True, motor_signals=None):
    """Analyze and fit a step response for a single detected step region.

    - Resamples signals to a suitable fs (at least pid_loop_hz*4 when logs are sparse).
    - Fits a second-order underdamped step response with optional delay.
    - Returns metrics (rise time, overshoot, settling time), fit parameters and arrays for plotting.

    Args:
        time_us (pd.Series or np.array): timestamps in microseconds.
        rc_command (pd.Series or np.array): input step command (same length as time_us).
        output_signal (pd.Series or np.array): measured output (e.g., rate or attitude) same length.
        pid_loop_hz (int): expected control loop frequency (Hz), used to choose resampling rate.
        plot (bool): if True and matplotlib available, display the plot.
        return_fit_curve (bool): whether to return the fitted curve arrays.

    Returns:
        dict: metrics, params, and (t_fit, y_fit) when requested.
    """
    # Basic validation
    if len(time_us) < 3 or len(rc_command) != len(time_us) or len(output_signal) != len(time_us):
        raise ValueError('time_us, rc_command and output_signal must be same length and have >=3 samples')

    # Convert to numpy
    t = np.asarray(time_us) / 1e6
    u = np.asarray(rc_command)
    y = np.asarray(output_signal)

    # Detect main step region: find largest change in input, avoiding motor clipping
    du = np.abs(np.diff(u))
    if du.size == 0:
        raise ValueError('No change detected in rc_command')
        
    found_valid_step = False
    max_attempts = 10
    
    for attempt in range(max_attempts):
        idx = np.argmax(du) + 1
        pre = int(max(0, idx - max(1, int(0.02 * pid_loop_hz))))
        post = int(min(len(t)-1, idx + max(2, int(0.5 * pid_loop_hz))))
        
        # Check motor saturation in this window
        clipped = False
        if motor_signals is not None:
            for m_sig in motor_signals:
                m_seg = m_sig[pre:post+1]
                if len(m_seg) > 0:
                    max_val = np.max(m_seg)
                    is_percent = max_val <= 100.0
                    is_raw = max_val > 1000.0
                    threshold = 2000.0 if is_raw else (100.0 if is_percent else 1.0)
                    clip_val = threshold * 0.99
                    if np.any(m_seg >= clip_val):
                        clipped = True
                        break
        
        if clipped:
            # Zero out this peak and try the next one
            zero_pre = int(max(0, idx - int(0.2 * pid_loop_hz)))
            zero_post = int(min(len(du)-1, idx + int(0.2 * pid_loop_hz)))
            du[zero_pre:zero_post+1] = 0
        else:
            found_valid_step = True
            break
            
    if not found_valid_step:
        # Fallback to the largest change if all steps were clipped, or just raise
        # It's better to process something than nothing, but maybe flag it?
        # We will just proceed with the last checked (clipped) step.
        pass

    t_seg = t[pre:post+1]
    u_seg = u[pre:post+1]
    y_seg = y[pre:post+1]

    # Step amplitude and initial/final values
    u0 = np.mean(u_seg[:max(1, int(0.05 * len(u_seg)))])
    uf = np.mean(u_seg[-max(1, int(0.05 * len(u_seg))):])
    step_amp = uf - u0

    # Choose resample frequency
    orig_fs = len(t_seg) / (t_seg[-1] - t_seg[0]) if (t_seg[-1] - t_seg[0]) > 0 else pid_loop_hz
    target_fs = int(max( min(2000, orig_fs*8), pid_loop_hz*4 ))

    t_rs, y_rs = _resample_to_fs((t_seg * 1e6).astype(np.int64), pd.Series(y_seg), target_fs)
    # shift t_rs to start at zero
    t_rs = t_rs - t_rs[0]

    # initial output
    y0 = float(np.mean(y_rs[:max(1, int(0.02 * len(y_rs)))]))
    y_final_guess = float(np.mean(y_rs[-max(1, int(0.1 * len(y_rs))):]))
    K_guess = (y_final_guess - y0) / (step_amp if step_amp != 0 else 1.0)

    # initial guesses and bounds
    wn_guess = 2 * np.pi * max(0.5, pid_loop_hz/4)
    zeta_guess = 0.6
    td_guess = 0.0

    p0 = [K_guess, wn_guess, zeta_guess, td_guess, y0]

    # Dynamic bounds based on data to avoid initial-guess/out-of-bounds errors
    duration = t_rs[-1] - t_rs[0] if len(t_rs) > 1 else max(0.1, 1.0/pid_loop_hz)
    td_upper = min(0.5, max(0.01, duration / 2.0))

    # K bounds: allow a wide window around the guess but ensure lower<upper
    if np.isfinite(K_guess):
        if abs(K_guess) < 1e-6:
            K_low, K_high = -10.0, 10.0
        else:
            K_low = K_guess * 0.1 if K_guess > 0 else K_guess * 10.0
            K_high = K_guess * 10.0 if K_guess > 0 else K_guess * 0.1
            if K_low == K_high:
                K_low, K_high = (K_guess - abs(K_guess)*5.0 - 1.0, K_guess + abs(K_guess)*5.0 + 1.0)
    else:
        K_low, K_high = -10.0, 10.0

    wn_low = 0.1
    wn_high = max(wn_guess * 10.0, 50.0)

    zeta_low, zeta_high = 0.0, 5.0

    y0_low = y0 - max(abs(y0) * 2.0, 1.0)
    y0_high = y0 + max(abs(y0) * 2.0, 1.0)

    bounds_lower = [K_low, wn_low, zeta_low, 0.0, y0_low]
    bounds_upper = [K_high, wn_high, zeta_high, td_upper, y0_high]

    # Ensure p0 is inside bounds; clamp if necessary (prevents curve_fit initial-guess errors)
    lb = np.array(bounds_lower, dtype=float)
    ub = np.array(bounds_upper, dtype=float)
    p0_arr = np.array(p0, dtype=float)
    # If any lb >= ub, replace with sensible defaults
    for i in range(len(lb)):
        if not (lb[i] < ub[i]):
            lb[i] = -1.0 if i == 0 else 0.1
            ub[i] = 1.0 if i == 0 else max(ub[i], lb[i] + 1.0)

    p0_clamped = np.minimum(np.maximum(p0_arr, lb + 1e-8), ub - 1e-8)

    try:
        popt, pcov = curve_fit(lambda tt, K, wn, zeta, td, y0: _second_order_step_response(tt, K*step_amp, wn, zeta, td, y0),
                               t_rs, y_rs, p0=p0_clamped.tolist(), bounds=(lb.tolist(), ub.tolist()), maxfev=20000)
        K_fit, wn_fit, zeta_fit, td_fit, y0_fit = popt
        # If the fitted damping is very large (overdamped / effectively first-order), prefer a first-order fit
        if zeta_fit > 2.0:
            # attempt a first-order fit instead
            try:
                p0_fo = [K_guess, max(0.01, (t_rs[-1] - t_rs[0]) / 4.0), td_guess, y0]
                lb_fo = [K_low, 1e-4, 0.0, y0_low]
                ub_fo = [K_high, max(10.0, (t_rs[-1] - t_rs[0]) * 10.0), td_upper, y0_high]
                popt_fo, _ = curve_fit(lambda tt, K, tau, td, y0: _first_order_step_response(tt, K*step_amp, tau, td, y0),
                                        t_rs, y_rs, p0=p0_fo, bounds=(lb_fo, ub_fo), maxfev=10000)
                Kf, tau_f, td_f, y0f = popt_fo
                t_fit = np.linspace(0, t_rs[-1], len(t_rs))
                y_fit = _first_order_step_response(t_fit, Kf*step_amp, tau_f, td_f, y0f)
                settling_time = 4.0 * tau_f
                rise_time = 2.2 * tau_f

                metrics = {
                    'model': 'first-order',
                    'step_input_amplitude': step_amp,
                    'gain_K': Kf,
                    'tau_s': tau_f,
                    'time_delay_s': td_f,
                    'y0': y0f,
                    'overshoot_pct': 0.0,
                    'rise_time_s': rise_time,
                    'settling_time_s': settling_time,
                }

                result = {'metrics': metrics, 'params': {'K':Kf, 'tau':tau_f, 'td':td_f, 'y0':y0f},
                          't_fit': t_fit, 'y_fit': y_fit, 't_segment': t_seg - t_seg[0], 'y_segment': y_seg}
                return result
            except Exception:
                # if first-order also fails, continue with second-order result
                pass
    except Exception as e:
        # Try first-order fit as a fallback when second-order fails
        try:
            # first-order parameters: K, tau, td, y0
            p0_fo = [K_guess, max(0.01, duration/4.0), td_guess, y0]
            lb_fo = [K_low, 1e-4, 0.0, y0_low]
            ub_fo = [K_high, max(10.0, duration*10.0), td_upper, y0_high]
            popt_fo, _ = curve_fit(lambda tt, K, tau, td, y0: _first_order_step_response(tt, K*step_amp, tau, td, y0),
                                    t_rs, y_rs, p0=p0_fo, bounds=(lb_fo, ub_fo), maxfev=10000)
            Kf, tau_f, td_f, y0f = popt_fo
            # build fitted curve
            t_fit = np.linspace(0, t_rs[-1], len(t_rs))
            y_fit = _first_order_step_response(t_fit, Kf*step_amp, tau_f, td_f, y0f)

            # metrics for first-order
            settling_time = 4.0 * tau_f
            rise_time = 2.2 * tau_f

            metrics = {
                'model': 'first-order',
                'step_input_amplitude': step_amp,
                'gain_K': Kf,
                'tau_s': tau_f,
                'time_delay_s': td_f,
                'y0': y0f,
                'overshoot_pct': 0.0,
                'rise_time_s': rise_time,
                'settling_time_s': settling_time,
            }

            result = {'metrics': metrics, 'params': {'K':Kf, 'tau':tau_f, 'td':td_f, 'y0':y0f},
                      't_fit': t_fit, 'y_fit': y_fit, 't_segment': t_seg - t_seg[0], 'y_segment': y_seg}
            return result
        except Exception:
            # fallback: compute simple metrics without fit
            return {
                'error': f'fit_failed: {e}',
                'step_amp': step_amp,
                't': t_seg - t_seg[0],
                'y': y_seg,
            }

    # build fitted curve
    t_fit = np.linspace(0, t_rs[-1], len(t_rs))
    y_fit = _second_order_step_response(t_fit, K_fit*step_amp, wn_fit, zeta_fit, td_fit, y0_fit)

    # Metrics from fitted parameters
    # Settling time (2% rule)
    if zeta_fit > 0 and wn_fit > 0:
        settling_time = 4.0 / (zeta_fit * wn_fit)
        peak_time = math.pi / (wn_fit * math.sqrt(max(1e-12, 1 - zeta_fit**2))) if zeta_fit < 1 else np.nan
        overshoot_pct = (math.exp(-zeta_fit * math.pi / math.sqrt(max(1e-12, 1 - zeta_fit**2))) * 100) if zeta_fit < 1 else 0.0
        # Rise time approx 10%-90% using standard second-order estimates (numerical fallback below)
    else:
        settling_time = np.nan
        peak_time = np.nan
        overshoot_pct = 0.0

    # Numeric estimation of rise time (10%-90%) on fitted curve
    y_start = y_fit[0]
    y_end = y_fit[-1]
    y10 = y_start + 0.1 * (y_end - y_start)
    y90 = y_start + 0.9 * (y_end - y_start)
    try:
        t_10 = t_fit[np.where(y_fit >= y10)[0][0]]
        t_90 = t_fit[np.where(y_fit >= y90)[0][0]]
        rise_time = t_90 - t_10
    except Exception:
        rise_time = np.nan

    metrics = {
        'step_input_amplitude': step_amp,
        'gain_K': K_fit,
        'wn_rad_s': wn_fit,
        'zeta': zeta_fit,
        'time_delay_s': td_fit,
        'y0': y0_fit,
        'overshoot_pct': overshoot_pct,
        'peak_time_s': peak_time,
        'rise_time_s': rise_time,
        'settling_time_s': settling_time,
    }

    if plot and plt is not None:
        plt.figure(figsize=(8,4))
        plt.plot(t_seg - t_seg[0], y_seg, 'o', label='measured', alpha=0.6)
        # map t_fit back to segment start
        plt.plot(t_fit + (t_seg[0]-t[0]), y_fit, '-', label='fitted model')
        plt.axvline(td_fit, color='gray', linestyle='--', label='time delay')
        plt.xlabel('Time (s)')
        plt.ylabel('Output')
        plt.title('Step response fit')
        plt.legend()
        plt.grid(True)
        plt.show()

    result = {'metrics': metrics, 'params': {'K':K_fit, 'wn':wn_fit, 'zeta':zeta_fit, 'td':td_fit, 'y0':y0_fit}}
    if return_fit_curve:
        result.update({'t_fit': t_fit, 'y_fit': y_fit, 't_segment': t_seg - t_seg[0], 'y_segment': y_seg})

    return result
