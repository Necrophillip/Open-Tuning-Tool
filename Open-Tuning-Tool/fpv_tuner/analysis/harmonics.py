import pandas as pd
import numpy as np

def compute_motor_harmonics(df, motor_poles, time_col, erpm_cols=None):
    """
    Derives real fundamental motor frequency (Hz) from eRPM
    (Bidirectional DShot telemetry), not from estimated noise peaks.

    eRPM -> mechanical Hz: rpm_mech = eRPM / (motor_poles / 2); hz = rpm_mech / 60

    Returns:
        DataFrame with columns time_s, h1_hz, h2_hz, h3_hz (average of available motors)
        or None if no eRPM telemetry is found in the log.
    """
    if erpm_cols is None:
        erpm_cols = [c for c in df.columns if c.startswith('eRPM[') or c.startswith('escRPM[')]
        
    if not erpm_cols or motor_poles is None:
        return None  # No real data, don't invent anything

    # Calculate mechanical RPM (eRPM / magnetic pole pairs)
    # Betaflight DShot telemetry logs eRPM / 100 to save bandwidth
    true_erpm = df[erpm_cols].mean(axis=1) * 100.0
    rpm_mech = true_erpm / (motor_poles / 2.0)
    h1_hz = rpm_mech / 60.0
    
    return pd.DataFrame({
        'time_s': df[time_col] / 1_000_000.0,
        'h1_hz': h1_hz,
        'h2_hz': h1_hz * 2,
        'h3_hz': h1_hz * 3,
    })
