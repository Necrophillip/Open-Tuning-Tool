import unittest

import numpy as np
import pandas as pd

from fpv_tuner.core.pid_tuning import dterm_analyzer, gyro_filter_analyzer, step_response_pid
from fpv_tuner.core.pid_tuning.tuning_context import (
    FLAG_REDUCES_FILTERING_BLOCKED, FLAG_REDUCES_FILTERING_RPM_COMPENSATED,
)
from fpv_tuner.core.pid_tuning.version_gyro_guard import build_tuning_context


def _headers(**overrides):
    base = {
        "Firmware revision": "Betaflight 2026.6.1 (6dbc4218f) STM32F405",
        "dterm_lpf1_static_hz": "75",
        "gyro_lpf1_static_hz": "250",
        "dshot_bidir": "ON",
        "rpm_filter_harmonics": "3",
        "rpm_filter_weights": "100,100,100",
    }
    base.update(overrides)
    return base


def _ctx(headers):
    return build_tuning_context(headers, gyro_model="ICM42688P")


def _noisy_dterm_df(rms=100.0):
    n = 4000
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "axisD[0]": rng.normal(0, rms, n),
        "axisD[1]": rng.normal(0, rms, n),
    })


class TestDtermAnalyzer(unittest.TestCase):
    def test_lowers_when_noisy(self):
        recs = dterm_analyzer.analyze(_noisy_dterm_df(), {}, _headers(), _ctx(_headers()))
        self.assertEqual(len(recs), 1)
        self.assertIn("dterm_lpf1_static_hz", recs[0].changes)
        self.assertLess(recs[0].changes["dterm_lpf1_static_hz"], 75)

    def test_floor_blocks_reduction(self):
        h = _headers(dterm_lpf1_static_hz="0")
        recs = dterm_analyzer.analyze(_noisy_dterm_df(), {}, h, _ctx(h))
        self.assertEqual(recs[0].changes, {})
        self.assertIn(FLAG_REDUCES_FILTERING_BLOCKED, recs[0].safety_flags)

    def test_clean_dterm_no_change(self):
        recs = dterm_analyzer.analyze(_noisy_dterm_df(rms=5.0), {}, _headers(), _ctx(_headers()))
        self.assertEqual(recs, [])


class TestGyroFilterAnalyzer(unittest.TestCase):
    def test_rpm_active_allows_reduction(self):
        h = _headers()
        recs = gyro_filter_analyzer.analyze(None, {}, h, _ctx(h))
        self.assertEqual(recs[0].changes.get("gyro_lpf1_static_hz"), 0)
        self.assertIn(FLAG_REDUCES_FILTERING_RPM_COMPENSATED, recs[0].safety_flags)

    def test_rpm_inactive_blocks(self):
        h = _headers(dshot_bidir="OFF", rpm_filter_weights="0,0,0")
        recs = gyro_filter_analyzer.analyze(None, {}, h, _ctx(h))
        self.assertEqual(recs[0].changes, {})
        self.assertIn(FLAG_REDUCES_FILTERING_BLOCKED, recs[0].safety_flags)

    def test_already_disabled(self):
        h = _headers(gyro_lpf1_static_hz="0")
        recs = gyro_filter_analyzer.analyze(None, {}, h, _ctx(h))
        self.assertEqual(recs, [])


class TestStepResponsePid(unittest.TestCase):
    def test_runs_without_error(self):
        n = 4000
        t = np.arange(n) * 250
        rc = np.zeros(n); rc[1000:] = 500
        gyro = np.zeros(n)
        gyro[1000:] = np.linspace(0, 500, n - 1000)
        df = pd.DataFrame({"time (us)": t, "rcCommand[0]": rc, "gyroADC[0]": gyro})
        recs = step_response_pid.analyze(df, {"p_roll": 45, "d_roll": 30}, _headers(), _ctx(_headers()))
        self.assertIsInstance(recs, list)


if __name__ == "__main__":
    unittest.main()
