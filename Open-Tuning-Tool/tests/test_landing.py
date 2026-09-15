import unittest
import pandas as pd
import numpy as np
from fpv_tuner.analysis.landing import measure_landing_bounce

class TestLandingDetector(unittest.TestCase):
    def test_no_landing_event(self):
        """
        Test that a dataframe representing a flight that never lands
        returns None cleanly without errors.
        """
        # Create a mock dataframe that never cuts throttle
        time_us = np.arange(0, 10_000_000, 1000) # 10 seconds, 1ms intervals
        # Throttle constantly at 1500 (hovering)
        throttle = np.full(len(time_us), 1500)
        # Random gyro
        gyro = np.random.normal(0, 5, len(time_us))

        df = pd.DataFrame({
            "time (us)": time_us,
            "rcCommand[3]": throttle,
            "gyroADC[0]": gyro
        })

        result = measure_landing_bounce(df)
        self.assertIsNone(result)

    def test_missing_columns(self):
        """Test with an empty or incorrectly formatted dataframe."""
        df = pd.DataFrame({"time (us)": [0, 1], "wrong_throttle": [1500, 1000]})
        result = measure_landing_bounce(df)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
