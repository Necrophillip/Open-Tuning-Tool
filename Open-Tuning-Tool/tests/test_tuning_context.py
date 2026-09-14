import unittest

from fpv_tuner.core.pid_tuning.version_gyro_guard import (
    build_tuning_context, extract_firmware_version, parse_status_gyro,
)
from fpv_tuner.core.pid_tuning.tuning_context import (
    FLAG_VERSION_MISMATCH, FLAG_GYRO_UNKNOWN_CONSERVATIVE, FLAG_CHIRP_UNSUPPORTED,
)
from fpv_tuner.core.cli import get_schema


def _headers(**overrides):
    base = {
        "Firmware revision": "Betaflight 2026.6.1 (6dbc4218f) STM32F405",
        "Board information": "SPBE SPEEDYBEEF405AIO",
        "DeviceUID": "0040004b3034510833363232",
        "simplified_pids_mode": "0",
        "simplified_dterm_filter": "0",
        "simplified_gyro_filter": "0",
        "debug_mode": "0",
    }
    base.update(overrides)
    return base


class TestFirmwareVersion(unittest.TestCase):
    def test_extract(self):
        self.assertEqual(extract_firmware_version(_headers()), "2026.6.1")
        self.assertEqual(
            extract_firmware_version(_headers(**{"Firmware revision": "Betaflight 4.5.0 (abc)"})),
            "4.5.0",
        )

    def test_parse_status_gyro(self):
        self.assertEqual(parse_status_gyro("Gyro: ICM42688P"), "ICM42688P")
        self.assertEqual(parse_status_gyro("Gyro: IIM-42652:0"), "IIM-42652")


class TestVersionBuckets(unittest.TestCase):
    def test_supported_45(self):
        ctx = build_tuning_context(
            _headers(**{"Firmware revision": "Betaflight 4.5.0 (abc)"}),
            gyro_model="ICM42688P", schema=get_schema("4.5.0"),
        )
        self.assertTrue(ctx.version_supported)
        self.assertNotIn(FLAG_VERSION_MISMATCH, ctx.warnings)
        self.assertEqual(ctx.tpa_model, "classic")

    def test_supported_2026(self):
        ctx = build_tuning_context(
            _headers(**{"Firmware revision": "Betaflight 2026.6.1 (abc)"}),
            gyro_model="ICM42688P", schema=get_schema("4.6.0"),
        )
        self.assertTrue(ctx.version_supported)
        self.assertEqual(ctx.tpa_model, "curve")

    def test_unsupported_old(self):
        ctx = build_tuning_context(
            _headers(**{"Firmware revision": "Betaflight 3.5.7 (abc)"}),
            gyro_model="ICM42688P",
        )
        self.assertFalse(ctx.version_supported)
        self.assertIn(FLAG_VERSION_MISMATCH, ctx.warnings)


class TestGyroGate(unittest.TestCase):
    def test_gyro_pre_fix_blocks(self):
        ctx = build_tuning_context(
            _headers(**{"Firmware revision": "Betaflight 4.5.0 (abc)"}),
            gyro_model="IIM-42652",
        )
        self.assertIn(FLAG_GYRO_UNKNOWN_CONSERVATIVE, ctx.warnings)
        self.assertIn(FLAG_VERSION_MISMATCH, ctx.warnings)

    def test_gyro_post_fix_ok(self):
        ctx = build_tuning_context(
            _headers(**{"Firmware revision": "Betaflight 2026.6.1 (abc)"}),
            gyro_model="IIM-42652",
        )
        self.assertNotIn(FLAG_GYRO_UNKNOWN_CONSERVATIVE, ctx.warnings)

    def test_gyro_unknown_conservative(self):
        ctx = build_tuning_context(_headers())
        self.assertTrue(ctx.gyro_model_unknown)
        self.assertIn(FLAG_GYRO_UNKNOWN_CONSERVATIVE, ctx.warnings)


class TestSlidersAndChirp(unittest.TestCase):
    def test_sliders_active(self):
        ctx = build_tuning_context(_headers(**{"simplified_pids_mode": "2"}))
        self.assertTrue(ctx.uses_simplified_sliders)

    def test_sliders_inactive(self):
        ctx = build_tuning_context(_headers())
        self.assertFalse(ctx.uses_simplified_sliders)

    def test_chirp_detected(self):
        headers = _headers(
            debug_mode="19",
            **{"chirp_lag_freq_hz": "5"},
        )
        ctx = build_tuning_context(
            headers,
            config={"debug_mode_chirp_values": [19], "supported_version_prefixes": ["2026."]},
        )
        self.assertTrue(ctx.chirp_detected)


if __name__ == "__main__":
    unittest.main()
