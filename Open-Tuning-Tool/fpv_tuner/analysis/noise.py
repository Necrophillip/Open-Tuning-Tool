import numpy as np
import pandas as pd
from scipy.signal import welch, spectrogram
from scipy.ndimage import gaussian_filter

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


def calculate_throttle_noise_heatmap(noise_series, throttle_series, time_series_us,
                                     n_throttle_bins=40, n_freq_bins=128,
                                     freq_min=0, freq_max=None, nperseg=256):
    """
    Calculate a 2D heatmap of noise power: X=throttle, Y=frequency, Color=power.

    The signal is sliced into segments, each assigned to a throttle bin. A PSD
    is computed per segment and results are averaged per throttle bin.

    Args:
        noise_series (pd.Series): Signal to analyse (gyro, D-term, ...).
        throttle_series (pd.Series): Throttle / motor command in percent (0-100).
        time_series_us (pd.Series): Time column in microseconds.
        n_throttle_bins (int): Number of throttle bins.
        n_freq_bins (int): Number of frequency bins in the output.
        freq_min (float): Minimum frequency to include.
        freq_max (float|None): Maximum frequency (defaults to Nyquist).
        nperseg (int): Welch segment length.

    Returns:
        (throttle_centers, freq_bins, heatmap_2d) or (None, None, None)
        heatmap_2d shape = (n_freq_bins, n_throttle_bins), values in dB.
    """
    # Drop NaN and infinite values
    throttle_clean = throttle_series.replace([np.inf, -np.inf], np.nan)
    mask = noise_series.notna() & throttle_clean.notna() & time_series_us.notna()
    noise = noise_series[mask].values
    throttle = throttle_clean[mask].values.astype(float)
    time_us = time_series_us[mask].values

    if len(noise) < nperseg * 2:
        print(f"  [heatmap] Not enough data: {len(noise)} samples, need >= {nperseg * 2}")
        return None, None, None

    # If throttle is constant, spread it artificially to avoid empty bins
    if np.ptp(throttle) < 1e-6:
        print("  [heatmap] Throttle is constant, using uniform distribution")
        throttle = np.linspace(0, 100, len(throttle))

    fs = get_sampling_frequency(pd.Series(time_us))
    if freq_max is None:
        freq_max = fs / 2.0

    # --- Segment the signal ---
    n_samples = len(noise)
    hop = nperseg // 2
    segments = []
    for start in range(0, n_samples - nperseg + 1, hop):
        end = start + nperseg
        seg_noise = noise[start:end]
        seg_throttle = np.mean(throttle[start:end])
        segments.append((seg_throttle, seg_noise))

    if not segments:
        return None, None, None

    # --- Compute PSD per segment ---
    window = np.hanning(nperseg)
    freqs_out = np.linspace(freq_min, freq_max, n_freq_bins)

    # Assign segments to throttle bins
    throttle_min, throttle_max = 0.0, 100.0
    throttle_edges = np.linspace(throttle_min, throttle_max, n_throttle_bins + 1)
    throttle_centers = 0.5 * (throttle_edges[:-1] + throttle_edges[1:])

    # Accumulate PSD values per throttle bin
    psd_accumulator = {i: [] for i in range(n_throttle_bins)}

    for seg_throttle, seg_noise in segments:
        # FFT-based PSD for this segment
        seg_windowed = seg_noise * window
        fft_vals = np.fft.rfft(seg_windowed)
        psd_raw = (np.abs(fft_vals) ** 2) / (fs * np.sum(window ** 2))
        fft_freqs = np.fft.rfftfreq(nperseg, d=1.0 / fs)

        # Interpolate to target frequency bins
        valid = (fft_freqs >= freq_min) & (fft_freqs <= freq_max)
        if not np.any(valid):
            continue
        psd_interp = np.interp(freqs_out, fft_freqs[valid], psd_raw[valid])

        # Find throttle bin
        bin_idx = np.searchsorted(throttle_edges, seg_throttle, side='right') - 1
        bin_idx = np.clip(bin_idx, 0, n_throttle_bins - 1)
        psd_accumulator[bin_idx].append(psd_interp)

    # Average per bin and convert to dB
    heatmap = np.full((n_freq_bins, n_throttle_bins), np.nan)
    for bin_idx, psd_list in psd_accumulator.items():
        if psd_list:
            avg_psd = np.mean(psd_list, axis=0)
            heatmap[:, bin_idx] = 10.0 * np.log10(avg_psd + 1e-12)

    # Fill NaN columns by interpolating from neighbours
    for col in range(n_throttle_bins):
        if np.all(np.isnan(heatmap[:, col])):
            # Find nearest non-NaN columns
            left = col - 1
            right = col + 1
            while left >= 0 and np.all(np.isnan(heatmap[:, left])):
                left -= 1
            while right < n_throttle_bins and np.all(np.isnan(heatmap[:, right])):
                right += 1

            if left >= 0 and right < n_throttle_bins:
                # Linear interpolation between left and right
                alpha = (col - left) / (right - left)
                heatmap[:, col] = (1 - alpha) * heatmap[:, left] + alpha * heatmap[:, right]
            elif left >= 0:
                heatmap[:, col] = heatmap[:, left]
            elif right < n_throttle_bins:
                heatmap[:, col] = heatmap[:, right]

    # Replace any remaining NaN with the global minimum
    if np.any(np.isnan(heatmap)):
        min_val = np.nanmin(heatmap) if not np.all(np.isnan(heatmap)) else -120.0
        heatmap = np.nan_to_num(heatmap, nan=min_val)

    # Light Gaussian smoothing for a nicer look
    heatmap = gaussian_filter(heatmap, sigma=1.0)

    return throttle_centers, freqs_out, heatmap


def calculate_pre_post_filter_psd(df, time_col, axis_idx, nperseg=256):
    """
    Calculate PSD for both pre-filter (gyroUnfilt) and post-filter (gyroADC)
    signals for a given axis.

    Args:
        df (pd.DataFrame): The loaded log DataFrame.
        time_col (str): Name of the time column.
        axis_idx (int): 0=Roll, 1=Pitch, 2=Yaw.
        nperseg (int): Welch segment length.

    Returns:
        dict with keys 'freq', 'psd_pre', 'psd_post' or None if columns not found.
    """
    time_us = df[time_col]
    result = {}

    pre_names = [f'gyroUnfilt[{axis_idx}]']
    post_names = [f'gyroADC[{axis_idx}]']

    pre_col = next((c for c in pre_names if c in df.columns), None)
    post_col = next((c for c in post_names if c in df.columns), None)

    if pre_col is None and post_col is None:
        return None

    if post_col:
        data = df[post_col].dropna()
        if not data.empty:
            fs = get_sampling_frequency(time_us)
            try:
                freq, psd = welch(data.values, fs, nperseg=nperseg)
                result['freq'] = freq
                result['psd_post'] = psd
            except Exception:
                pass

    if pre_col:
        data = df[pre_col].dropna()
        if not data.empty:
            fs = get_sampling_frequency(time_us)
            try:
                freq, psd = welch(data.values, fs, nperseg=nperseg)
                if 'freq' not in result:
                    result['freq'] = freq
                result['psd_pre'] = psd
            except Exception:
                pass

    return result if result else None


def calculate_pre_post_filter_spectrogram(df, time_col, axis_idx, nperseg=256):
    """
    Calculate spectrograms for both pre-filter and post-filter signals.

    Returns:
        dict with keys 'freqs', 'times', 'Sxx_pre', 'Sxx_post' or None.
    """
    time_us = df[time_col]
    result = {}

    pre_col = next((c for c in [f'gyroUnfilt[{axis_idx}]'] if c in df.columns), None)
    post_col = next((c for c in [f'gyroADC[{axis_idx}]'] if c in df.columns), None)

    if pre_col is None and post_col is None:
        return None

    if post_col:
        data = df[post_col].dropna()
        if not data.empty:
            fs = get_sampling_frequency(time_us)
            try:
                freqs, times, Sxx = spectrogram(data.values, fs, nperseg=nperseg)
                result['freqs'] = freqs
                result['times'] = times
                result['Sxx_post'] = Sxx
            except Exception:
                pass

    if pre_col:
        data = df[pre_col].dropna()
        if not data.empty:
            fs = get_sampling_frequency(time_us)
            try:
                freqs, times, Sxx = spectrogram(data.values, fs, nperseg=nperseg)
                if 'freqs' not in result:
                    result['freqs'] = freqs
                    result['times'] = times
                result['Sxx_pre'] = Sxx
            except Exception:
                pass

    return result if result else None
