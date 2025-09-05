import numpy as np
from scipy.optimize import curve_fit

# ------------------------------
# System Response Models
# ------------------------------
def first_order_step_model(t, K, tau):
    """ First-order system step response model. """
    if tau == 0:
        return K * np.ones_like(t)
    return K * (1 - np.exp(-t / tau))

def second_order_step_model(t, K, wn, zeta):
    """ Second-order system step response model. """
    if wn <= 0 or zeta <= 0:
        return np.zeros_like(t)
    if np.isclose(zeta, 1):
        return K * (1 - (1 + wn * t) * np.exp(-wn * t))
    elif zeta > 1:
        p1 = wn * (zeta - np.sqrt(zeta**2 - 1))
        p2 = wn * (zeta + np.sqrt(zeta**2 - 1))
        return K * (1 + (p1 * np.exp(-p2 * t) - p2 * np.exp(-p1 * t)) / (p2 - p1))
    else:
        wd = wn * np.sqrt(1 - zeta**2)
        phi = np.arccos(zeta)
        return K * (1 - (1 / np.sqrt(1 - zeta**2)) * np.exp(-zeta * wn * t) * np.sin(wd * t + phi))

# ------------------------------
# Main Analysis Function
# ------------------------------
def analyze_axis_response(axis_name, time, rc_command, gyro_response, threshold_ratio=0.7):
    """
    Analyzes a single axis to find the average, normalized step response and fit system models.
    """
    dt = np.mean(np.diff(time))
    if np.isnan(dt) or dt == 0:
        return {"error": "Invalid time data"}

    # --- Step 1: Detect large deflections ---
    max_rc = np.max(np.abs(rc_command))
    if max_rc == 0:
        return {"error": "No RC command input"}

    thresh = threshold_ratio * max_rc
    deflex_mask = np.abs(rc_command) > thresh
    starts = np.where(np.diff(deflex_mask.astype(int)) == 1)[0]

    if len(starts) == 0:
        return {"error": f"No deflections found with current sensitivity."}

    # --- Step 2: Extract, normalize, and average responses ---
    initial_window = int(0.2 / dt) # 200ms window
    responses = []
    for idx in starts:
        if idx + initial_window > len(time) or idx < 5: continue

        # Use a more robust delta and prevent division by zero
        delta_u = rc_command[idx + 5] - rc_command[idx - 5]
        if delta_u == 0: continue

        t_win = time[idx:idx + initial_window] - time[idx]
        y_win = gyro_response[idx:idx + initial_window]
        y_norm = (y_win - y_win[0]) / delta_u
        responses.append(y_norm)

    if not responses:
        return {"error": "Could not extract any valid response windows."}

    min_len = min(len(r) for r in responses)
    t_avg = time[:min_len] - time[0]
    y_avg = np.mean([r[:min_len] for r in responses], axis=0)

    # --- Step 3: Fit models ---
    results = {"t_avg": t_avg, "y_avg": y_avg, "popt1": None, "popt2": None, "num_responses": len(responses)}
    try:
        popt1, _ = curve_fit(first_order_step_model, t_avg, y_avg, p0=[np.median(y_avg), 0.05], bounds=([0, 0], [2, 1]))
        results["popt1"] = popt1
    except Exception as e:
        print(f"1st order fit failed for {axis_name}: {e}")

    try:
        p0 = [np.median(y_avg), 100, 0.7]
        bounds = ([0, 1, 0.1], [2, 1000, 1.5])
        popt2, _ = curve_fit(second_order_step_model, t_avg, y_avg, p0=p0, bounds=bounds, maxfev=5000)
        results["popt2"] = popt2
    except Exception as e:
        print(f"2nd order fit failed for {axis_name}: {e}")

    return results
