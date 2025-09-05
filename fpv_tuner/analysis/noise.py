import numpy as np
import pandas as pd
from scipy.signal import welch, spectrogram

def get_sampling_frequency(time_series_us):
    """
    Calculates the average sampling frequency from a time series in microseconds.

    Args:
        time_series_us (pd.Series): The time data in microseconds.

    Returns:
        float: The average sampling frequency in Hz, or a default if calculation fails.
    """
    if time_series_us is None or len(time_series_us) < 2:
        return 2000.0  # Return a sensible default

    # Calculate the differences between consecutive time points in seconds
    time_diffs_s = time_series_us.diff() / 1_000_000

    # Calculate the average sampling period and then the frequency
    avg_period = time_diffs_s.mean()

    if pd.isna(avg_period) or avg_period <= 0:
        # Fallback for logs with irregular time steps
        total_duration_s = (time_series_us.iloc[-1] - time_series_us.iloc[0]) / 1_000_000
        if total_duration_s > 0:
            return (len(time_series_us) - 1) / total_duration_s
        return 2000.0  # Final fallback

    fs = 1.0 / avg_period
    return fs

def calculate_psd(data_series, time_series_us, nperseg=256):
    """
    Calculates the Power Spectral Density (PSD) of a signal using Welch's method.

    Args:
        data_series (pd.Series): The input signal data (e.g., gyro).
        time_series_us (pd.Series): The time data in microseconds, for calculating fs.
        nperseg (int): Length of each segment for Welch's method.

    Returns:
        A tuple containing (frequencies, psd) or (None, None) on error.
    """
    # Remove any NaN values that would crash the calculation
    data = data_series.dropna()
    if data.empty:
        return None, None

    fs = get_sampling_frequency(time_series_us)

    # Welch's method for a cleaner spectrum
    try:
        # Convert pandas Series to NumPy array for max compatibility with scipy
        frequencies, psd = welch(data.values, fs, nperseg=nperseg)
        return frequencies, psd
    except Exception as e:
        print(f"Error calculating PSD: {e}")
        return None, None

def calculate_signal_stats(data_series, frequencies, psd):
    """
    Calculates a set of statistics for a given signal and its PSD.
    """
    if data_series is None or data_series.empty:
        return {}

    # Time-domain stats
    peak = data_series.max()
    rms = np.sqrt(np.mean(data_series**2))
    std_dev = data_series.std()

    stats = {
        "Peak": f"{peak:.2f}",
        "RMS": f"{rms:.2f}",
        "Std. Dev.": f"{std_dev:.2f}",
    }

    # Frequency-domain stats
    if frequencies is not None and psd is not None and len(frequencies) > 0 and len(psd) > 0:
        max_noise_idx = np.argmax(psd)
        max_noise_freq = frequencies[max_noise_idx]
        # The PSD value is already power, not dB yet.
        stats["Max Noise Peak"] = f"{max_noise_freq:.1f} Hz"

    return stats

def calculate_spectrogram(data_series, time_series_us, nperseg=256):
    """
    Calculates the Spectrogram of a signal.
    """
    if data_series is None or data_series.empty:
        return None, None, None

    # Remove any NaN values that would crash the calculation
    data = data_series.dropna()
    if data.empty:
        return None, None, None

    fs = get_sampling_frequency(time_series_us)

    try:
        # Using .values to ensure it's a NumPy array
        frequencies, times, Sxx = spectrogram(data.values, fs, nperseg=nperseg)
        return frequencies, times, Sxx
    except Exception as e:
        print(f"Error calculating spectrogram: {e}")
        return None, None, None
