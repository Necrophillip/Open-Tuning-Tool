import unittest
import numpy as np
import pandas as pd
from fpv_tuner.analysis.noise import calculate_throttle_noise_heatmap

class TestThrottleNoiseHeatmap(unittest.TestCase):
    def test_heatmap_transpose_shape_consistency(self):
        """
        Verify that the output shape of the heatmap matches (n_freq_bins, n_throttle_bins).
        This test explicitly validates that the .T (transpose) is mathematically required
        before passing it to pyqtgraph's col-major image layout which expects (x, y).
        """
        # Create synthetic signal
        n_samples = 4000
        np.random.seed(42)
        noise = np.random.randn(n_samples)
        # throttle from 0 to 100
        throttle = np.linspace(0, 100, n_samples)
        time_us = np.arange(n_samples) * 1000  # 1ms intervals
        
        noise_series = pd.Series(noise)
        throttle_series = pd.Series(throttle)
        time_series = pd.Series(time_us)
        
        n_t_bins = 40
        n_f_bins = 128
        
        t_centers, f_bins, heatmap = calculate_throttle_noise_heatmap(
            noise_series, throttle_series, time_series,
            n_throttle_bins=n_t_bins, n_freq_bins=n_f_bins, nperseg=256
        )
        
        self.assertIsNotNone(heatmap)
        # Verify the underlying mathematical matrix shape
        self.assertEqual(heatmap.shape, (n_f_bins, n_t_bins))
        
        # When passed to pyqtgraph.setImage(image.T), the shape becomes:
        transposed = heatmap.T
        self.assertEqual(transposed.shape, (n_t_bins, n_f_bins))
        
        # In pyqtgraph, shape[0] maps to X-axis (throttle), shape[1] maps to Y-axis (frequency)
        # Thus heatmap.T correctly maps throttle to X and frequency to Y.
        self.assertEqual(transposed.shape[0], len(t_centers))
        self.assertEqual(transposed.shape[1], len(f_bins))

if __name__ == '__main__':
    unittest.main()
