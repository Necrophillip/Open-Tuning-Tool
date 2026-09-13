import unittest

from fpv_tuner.core.cli import (
    get_schema, validate_change, clamp_value, normalize_name,
)


class TestSchemaCatalog(unittest.TestCase):
    def test_version_routing(self):
        self.assertEqual(get_schema("4.5.0").version, "4.5.0")
        self.assertEqual(get_schema("4.6.0").version, "4.6.0")
        self.assertEqual(get_schema().version, "4.6.0")  # latest fallback

    def test_contains_modern_names(self):
        s = get_schema("4.5.0")
        for name in (
            "gyro_lpf1_static_hz", "dterm_lpf1_static_hz",
            "dyn_notch_count", "p_roll", "dterm_notch_hz",
        ):
            self.assertIn(name, s, f"missing {name}")

    def test_no_legacy_names(self):
        s = get_schema("4.5.0")
        self.assertNotIn("gyro_lowpass_hz", s)
        self.assertNotIn("dterm_lowpass_hz", s)

    def test_normalize_legacy_alias(self):
        s = get_schema("4.5.0")
        self.assertEqual(normalize_name(s, "gyro_lowpass_hz"), "gyro_lpf1_static_hz")
        self.assertEqual(normalize_name(s, "dterm_lowpass_hz"), "dterm_lpf1_static_hz")


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.s = get_schema("4.5.0")

    def test_valid_numeric(self):
        self.assertEqual(validate_change(self.s, "p_roll", "47"), [])

    def test_out_of_range(self):
        self.assertTrue(validate_change(self.s, "p_roll", "999"))
        self.assertTrue(validate_change(self.s, "gyro_lpf1_static_hz", "9999"))

    def test_enum(self):
        self.assertEqual(validate_change(self.s, "gyro_lpf1_type", "PT1"), [])
        self.assertTrue(validate_change(self.s, "gyro_lpf1_type", "NOPE"))

    def test_clamp(self):
        self.assertEqual(clamp_value(self.s.get("p_roll"), "999"), "250")
        self.assertEqual(clamp_value(self.s.get("gyro_lpf1_static_hz"), "9999"), "1000")

    def test_unknown_name(self):
        from fpv_tuner.core.cli import CliValueError
        with self.assertRaises(CliValueError):
            normalize_name(self.s, "does_not_exist")


if __name__ == "__main__":
    unittest.main()
