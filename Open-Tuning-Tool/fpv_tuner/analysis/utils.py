import numpy as np

def apply_smoothing(data, level):
    """
    Applies a simple moving average filter to the data.

    Args:
        data (np.ndarray): The input data series.
        level (int): The window size for the moving average. If level is 0 or 1,
                     the original data is returned.

    Returns:
        np.ndarray: The smoothed data.
    """
    if level <= 1:
        return data

    # Use 'valid' mode to handle edges, then pad to maintain original length
    # This is a common way to apply a causal moving average
    window = np.ones(level) / level
    smoothed = np.convolve(data, window, mode='valid')

    # Pad the result to match the original data length
    pad_size = len(data) - len(smoothed)
    # Pad at the beginning to simulate a causal filter
    padded_smoothed = np.pad(smoothed, (pad_size, 0), 'edge')

    return padded_smoothed
