import unittest

from fpv_tuner.core.diagnostics import Finding, Severity, Category
from fpv_tuner.core.prescription import generate_prescription
from fpv_tuner.core.cli import get_schema, validate_change


class TestPrescription(unittest.TestCase):
    def _gyro_noise(self, rms):
        return [Finding(
            severity=Severity.CRITICAL if rms > 50 else Severity.WARNING,
            category=Category.GYRO_NOISE, title="noise", explanation="",
            data={"axis_name": "Roll", "rms": rms},
        )]

    def test_emits_modern_names(self):
        rx = generate_prescription(self._gyro_noise(60), cli_settings=None, cli_version="4.5.0")
        names = {c.setting for c in rx.changes}
        self.assertIn("gyro_lpf1_dyn_min_hz", names)
        self.assertIn("dterm_lpf1_dyn_min_hz", names)
        self.assertNotIn("gyro_lowpass_hz", names)
        self.assertNotIn("dterm_lowpass_hz", names)

    def test_all_changes_valid_against_schema(self):
        rx = generate_prescription(self._gyro_noise(60), cli_settings=None, cli_version="4.5.0")
        schema = get_schema("4.5.0")
        for c in rx.changes:
            self.assertEqual(
                validate_change(schema, c.setting, c.new_value), [],
                f"invalid change: {c.setting}={c.new_value}",
            )
        self.assertEqual(rx.warnings, [])

    def test_no_findings_no_changes(self):
        rx = generate_prescription([], cli_settings=None, cli_version="4.5.0")
        self.assertEqual(rx.changes, [])

    def test_pid_suggestion_overshoot(self):
        findings = [Finding(
            severity=Severity.WARNING, category=Category.PID, title="SR", explanation="",
            data={"axis": "roll", "axis_name": "Roll", "overshoot_pct": 25.0, "rise_time_s": None},
        )]
        rx = generate_prescription(findings, {"p_roll": "45", "d_roll": "30"}, cli_version="4.5.0")
        by_name = {c.setting: c for c in rx.changes}
        self.assertIn("p_roll", by_name)
        self.assertLess(int(by_name["p_roll"].new_value), 45)
        self.assertGreater(int(by_name["d_roll"].new_value), 30)

    def test_pid_suggestion_slow_rise(self):
        findings = [Finding(
            severity=Severity.WARNING, category=Category.PID, title="SR", explanation="",
            data={"axis": "pitch", "axis_name": "Pitch", "overshoot_pct": 0.0, "rise_time_s": 0.3},
        )]
        rx = generate_prescription(findings, {"p_pitch": "47", "d_pitch": "32"}, cli_version="4.5.0")
        by_name = {c.setting: c for c in rx.changes}
        self.assertIn("p_pitch", by_name)
        self.assertGreater(int(by_name["p_pitch"].new_value), 47)


if __name__ == "__main__":
    unittest.main()
