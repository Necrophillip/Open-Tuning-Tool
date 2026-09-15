import unittest
import pandas as pd
import numpy as np

from fpv_tuner.core.pid_tuning.feedforward_analyzer import analyze
from fpv_tuner.core.pid_tuning.models import SubRecommendation

class TestFeedforwardAnalyzer(unittest.TestCase):
    def test_sharp_inputs_low_ff(self):
        # Create a synthetic dataframe with sharp setpoint inputs
        time = np.linspace(0, 1, 1000)
        setpoint = np.zeros(1000)
        setpoint[200:250] = 300 # Sharp step
        setpoint[500:550] = -300

        # Gyro lags behind
        gyro = np.zeros(1000)
        gyro[220:270] = 200

        df = pd.DataFrame({
            "rcCommand[0]": setpoint,
            "gyroADC[0]": gyro,
            "rcCommand[1]": setpoint,
            "gyroADC[1]": gyro,
            "rcCommand[2]": np.zeros(1000),
            "gyroADC[2]": np.zeros(1000),
        })

        # Test with very low FF
        pids = {"f_roll": 20, "f_pitch": 40}
        recs = analyze(df, pids, {}, None, rules={})
        
        self.assertTrue(len(recs) > 0)
        roll_rec = next((r for r in recs if "f_roll" in r.changes), None)
        self.assertIsNotNone(roll_rec)
        self.assertEqual(roll_rec.changes["f_roll"], 26) # 60 is the hardcoded minimum target

        pitch_rec = next((r for r in recs if "f_pitch" in r.changes), None)
        self.assertIsNotNone(pitch_rec)
        self.assertEqual(pitch_rec.changes["f_pitch"], 52)

    def test_sharp_inputs_high_ff(self):
        # Create a synthetic dataframe with sharp setpoint inputs
        time = np.linspace(0, 1, 1000)
        setpoint = np.zeros(1000)
        setpoint[200:250] = 300 # Sharp step
        
        gyro = np.zeros(1000)

        df = pd.DataFrame({
            "rcCommand[0]": setpoint,
            "gyroADC[0]": gyro,
            "rcCommand[1]": setpoint,
            "gyroADC[1]": gyro,
            "rcCommand[2]": np.zeros(1000),
            "gyroADC[2]": np.zeros(1000),
        })

        # Test with high FF
        pids = {"f_roll": 200, "f_pitch": 180}
        recs = analyze(df, pids, {}, None, rules={})
        
        self.assertTrue(len(recs) > 0)
        roll_rec = next((r for r in recs if "f_roll" in r.changes), None)
        self.assertIsNotNone(roll_rec)
        self.assertEqual(roll_rec.changes["f_roll"], 160) # 200 * 0.8

        pitch_rec = next((r for r in recs if "f_pitch" in r.changes), None)
        self.assertIsNotNone(pitch_rec)
        self.assertEqual(pitch_rec.changes["f_pitch"], 144) # 180 * 0.8

if __name__ == '__main__':
    unittest.main()
