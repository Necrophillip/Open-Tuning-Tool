import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

def find_step_responses(rc_command, time_us, threshold=300, min_step_duration_ms=40, pre_step_flat_ms=10, post_step_flat_ms=100):
    """
    Finds step-like movements in an RC command trace.
    (Copied and adapted from the main application)
    """
    if rc_command is None or time_us is None or rc_command.empty:
        return []

    time_s = time_us / 1_000_000
    fs = len(time_us) / (time_s.iloc[-1] - time_s.iloc[0]) if len(time_us) > 1 and (time_s.iloc[-1] - time_s.iloc[0]) > 0 else 2000
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

        if pre_step_segment.std() < 50 and post_step_segment.std() < 50:
            if end_idx - i > min_duration_indices:
                found_steps.append((start_idx, i, end_idx))
                last_step_end = end_idx

    return found_steps

def step_response_metrics(time, input_signal, output_signal):
    """
    Calculates key metrics for a step response.
    """
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
        outside_bounds = np.where(np.abs(output_signal - val_f_out) > settling_threshold)[0]
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


def main():
    # --- Configuration ---
    CSV_FILE = 'btfl_005.03.csv'
    AXES_MAPPING = {
        'Roll':  {'rc': 'rcCommand[0]', 'gyro': 'gyroADC[0]', 'dterm': 'axisD[0]'},
        'Pitch': {'rc': 'rcCommand[1]', 'gyro': 'gyroADC[1]', 'dterm': 'axisD[1]'},
        'Yaw':   {'rc': 'rcCommand[2]', 'gyro': 'gyroADC[2]', 'dterm': 'axisD[2]'},
    }
    STEP_DETECTION_THRESHOLD = 200

    # --- Load and Clean Data ---
    try:
        df = pd.read_csv(CSV_FILE, header=1) # Assuming header is on the second line
    except FileNotFoundError:
        print(f"Error: Log file '{CSV_FILE}' not found. Please make sure it's in the same directory as the script.")
        return

    df.columns = df.columns.str.strip()

    # --- Analysis and Plotting ---
    fig, axes = plt.subplots(3, 1, figsize=(15, 12), sharex=True)
    fig.suptitle('Step Response Analysis', fontsize=16)

    all_metrics = []

    for i, (axis_name, cols) in enumerate(AXES_MAPPING.items()):
        ax = axes[i]

        # Find the most significant step for this axis
        steps = find_step_responses(df[cols['rc']], df['time (us)'], threshold=STEP_DETECTION_THRESHOLD)
        if not steps:
            print(f"No significant steps found for {axis_name}.")
            ax.set_title(f"{axis_name} - No steps found")
            continue

        # Analyze the first (and likely most significant) step found
        start, step_idx, end = steps[0]

        time_slice = df['time (us)'].iloc[start:end].copy() / 1_000_000
        time_slice.reset_index(drop=True, inplace=True)
        rc_slice = df[cols['rc']].iloc[start:end].copy().reset_index(drop=True)
        gyro_slice = df[cols['gyro']].iloc[start:end].copy().reset_index(drop=True)
        dterm_slice = df[cols['dterm']].iloc[start:end].copy().reset_index(drop=True)

        # Plotting
        ax.plot(time_slice, rc_slice, label='RC Command (Input)', color='blue')
        ax.plot(time_slice, gyro_slice, label='Gyro Response (Output)', color='red')
        ax.plot(time_slice, dterm_slice, label='D-Term', color='green', linestyle='--')
        ax.set_title(f"{axis_name} Step Response")
        ax.set_ylabel("Value")
        ax.legend()
        ax.grid(True)

        # Calculate and store metrics
        metrics = step_response_metrics(time_slice, rc_slice, gyro_slice)
        metrics['Axis'] = axis_name
        all_metrics.append(metrics)

    plt.xlabel("Time (s)")
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig('step_response_plot.png')
    print("\n✅ Step response plot saved to 'step_response_plot.png'")

    # --- Print and Save Metrics ---
    if all_metrics:
        metrics_df = pd.DataFrame(all_metrics)
        metrics_df = metrics_df.set_index('Axis')

        print("\n--- Step Response Metrics ---")
        print(metrics_df.to_string(float_format="%.4f"))

        metrics_df.to_csv('step_response_metrics.csv')
        print("\n✅ Performance metrics saved to 'step_response_metrics.csv'")

if __name__ == '__main__':
    main()
