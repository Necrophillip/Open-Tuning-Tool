import unittest

from fpv_tuner.core.session_history import (
    derive_fc_id, build_revert_commands, SessionSnapshot,
)


class TestFcId(unittest.TestCase):
    def test_board_name_preferred(self):
        self.assertEqual(
            derive_fc_id(board_name="SPEEDYBEEF405AIO", manufacturer_id="SPBE"),
            "spbe-speedybeef405aio",
        )

    def test_fallback_board_target(self):
        self.assertEqual(
            derive_fc_id(board="STM32F405", target="F405"),
            "stm32f405-f405",
        )

    def test_unknown(self):
        self.assertEqual(derive_fc_id(), "unknown")


class TestRevert(unittest.TestCase):
    def test_revert_commands(self):
        snap = SessionSnapshot(session_id="abc", applied_changes=[
            {"setting": "p_roll", "old": "45", "new": "50"},
            {"setting": "gyro_lpf1_dyn_min_hz", "old": "250", "new": "240"},
        ])
        out = build_revert_commands(snap)
        self.assertIn("set p_roll = 45", out)
        self.assertIn("set gyro_lpf1_dyn_min_hz = 250", out)
        self.assertTrue(out.rstrip().endswith("save"))

    def test_revert_no_changes(self):
        snap = SessionSnapshot(session_id="x", applied_changes=[])
        self.assertIn("Nothing to revert", build_revert_commands(snap))


if __name__ == "__main__":
    unittest.main()
