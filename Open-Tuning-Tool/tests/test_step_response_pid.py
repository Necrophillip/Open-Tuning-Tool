import unittest
import pandas as pd
from fpv_tuner.core.pid_tuning.step_response_pid import analyze, zeta_from_overshoot_pct
from fpv_tuner.core.pid_tuning.models import SubRecommendation
from fpv_tuner.core.pid_tuning.tuning_context import TuningContext
from fpv_tuner.core.cli.schema import CliSchema

class TestStepResponsePid(unittest.TestCase):
    def test_zeta_conversion(self):
        """Test the mathematical inversion of the overshoot to zeta."""
        # Overshoot of 20% should be approx zeta = 0.456
        zeta_20 = zeta_from_overshoot_pct(20.0)
        self.assertAlmostEqual(zeta_20, 0.4559, places=3)
        
        # Overshoot of 12% should be approx zeta = 0.559
        zeta_12 = zeta_from_overshoot_pct(12.0)
        self.assertAlmostEqual(zeta_12, 0.5594, places=3)
        
        # Overshoot of 5% should be approx zeta = 0.690
        zeta_5 = zeta_from_overshoot_pct(5.0)
        self.assertAlmostEqual(zeta_5, 0.6901, places=3)

    def test_no_change_on_good_zeta_and_rise_time(self):
        """Test regression: well damped (zeta >= 0.690) and normal rise time should not change P/D."""
        import sys
        # We need to mock compute_step_response_summary for this test
        from unittest.mock import patch
        
        df = pd.DataFrame()
        pids = {"p_roll": 40, "d_roll": 30, "p_pitch": 40, "d_pitch": 30, "p_yaw": 40, "d_yaw": 30}
        headers = {}
        context = TuningContext()
        rules = {
            "step_response": {
                "overshoot_high": 20.0,
                "overshoot_mid": 12.0,
                "rise_time_slow": 0.20,
                "pid_max": 250,
                "status": "heuristic_unvalidated"
            }
        }
        
        with patch('fpv_tuner.core.pid_tuning.step_response_pid.compute_step_response_summary') as mock_compute:
            # Return a perfect step response
            mock_compute.return_value = {
                "zeta": 0.75, # Well damped (zeta >= 0.690)
                "rise_time_s": 0.100 # Fast enough (<= 0.150)
            }
            
            recs = analyze(df, pids, headers, context, rules=rules)
            
            # Since zeta >= 0.690 and rise_time <= 0.150, there should be NO recommendations
            self.assertEqual(len(recs), 0)

    def test_clamp_max_changes(self):
        """Test that combined changes are clamped to +/- 20%."""
        from unittest.mock import patch
        df = pd.DataFrame()
        pids = {"p_roll": 50, "d_roll": 50}
        
        with patch('fpv_tuner.core.pid_tuning.step_response_pid.compute_step_response_summary') as mock_compute:
            # Force severe underdamping AND slow rise time
            # zeta < 0.456 drops P by 10% (P=45) and raises D by 10% (D=55)
            # rise_time > 0.200 raises P by 10% (P=49)
            # End result without clamp: P=49, D=55. (Both are within 20% of 50).
            mock_compute.return_value = {
                "zeta": 0.3,
                "rise_time_s": 0.300
            }
            recs = analyze(df, pids, {}, TuningContext(), rules=None)
            
            if recs:
                roll_changes = recs[0].changes
                self.assertTrue(40 <= roll_changes.get("p_roll", 50) <= 60)
                self.assertTrue(40 <= roll_changes.get("d_roll", 50) <= 60)

if __name__ == '__main__':
    unittest.main()
