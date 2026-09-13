import unittest

from fpv_tuner.core.serial.msc import filter_blackbox_files
from fpv_tuner.core.serial.autodetect import is_flight_controller
from fpv_tuner.core.serial.ports import SerialPortInfo


class TestBlackboxFilter(unittest.TestCase):
    def test_excludes_all_file(self):
        files = [
            "/Volumes/BETAFLT/btfl_all.bbl",
            "/Volumes/BETAFLT/btfl_001.bbl",
            "/Volumes/BETAFLT/btfl_002.bbl",
        ]
        result = filter_blackbox_files(files)
        self.assertEqual(result, [
            "/Volumes/BETAFLT/btfl_001.bbl",
            "/Volumes/BETAFLT/btfl_002.bbl",
        ])

    def test_case_insensitive(self):
        self.assertEqual(filter_blackbox_files(["/v/btfl_ALL.bbl", "/v/a.bbl"]), ["/v/a.bbl"])

    def test_no_all_keeps_all(self):
        files = ["/v/btfl_001.bbl", "/v/btfl_002.bbl"]
        self.assertEqual(filter_blackbox_files(files), files)


class TestAutodetect(unittest.TestCase):
    def test_betaflight_by_vid_pid(self):
        p = SerialPortInfo(device="/dev/x", vid=0x0483, pid=0x5740)
        self.assertTrue(is_flight_controller(p))

    def test_betaflight_by_description(self):
        p = SerialPortInfo(device="/dev/x", description="Betaflight - SPEEDYBEEF405AIO")
        self.assertTrue(is_flight_controller(p))

    def test_not_fc(self):
        p = SerialPortInfo(device="/dev/x", description="Bluetooth-Incoming-Port")
        self.assertFalse(is_flight_controller(p))


if __name__ == "__main__":
    unittest.main()
