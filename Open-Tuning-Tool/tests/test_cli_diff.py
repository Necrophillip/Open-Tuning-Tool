import unittest

from fpv_tuner.core.cli_diff import CliDiff, DiffEntry, format_cli_commands
from fpv_tuner.core.cli import get_schema


class TestFormatCliCommands(unittest.TestCase):
    def test_scope_grouping(self):
        diff = CliDiff(entries=[
            DiffEntry(setting="gyro_lpf1_dyn_min_hz", old_value="250", new_value="150", kind="changed"),
            DiffEntry(setting="p_roll", old_value="47", new_value="55", kind="changed"),
        ])
        out = format_cli_commands(diff, schema=get_schema("4.5.0"))
        self.assertIn("set gyro_lpf1_dyn_min_hz = 150", out)
        self.assertIn("profile 0", out)
        self.assertIn("set p_roll = 55", out)
        self.assertTrue(out.rstrip().endswith("save"))

    def test_master_only_no_profile_selector(self):
        diff = CliDiff(entries=[
            DiffEntry(setting="dyn_notch_count", old_value="3", new_value="5", kind="changed"),
        ])
        out = format_cli_commands(diff, schema=get_schema("4.5.0"))
        self.assertNotIn("profile 0", out)

    def test_no_schema_falls_back_flat(self):
        diff = CliDiff(entries=[
            DiffEntry(setting="p_roll", old_value="47", new_value="55", kind="changed"),
        ])
        out = format_cli_commands(diff)
        self.assertIn("set p_roll = 55", out)
        self.assertNotIn("profile 0", out)

    def test_empty_diff(self):
        out = format_cli_commands(CliDiff())
        self.assertIn("No changes", out)


if __name__ == "__main__":
    unittest.main()
