import unittest

from fpv_tuner.core.serial.msp import (
    encode_msp, decode_msp, checksum, MSP_REBOOT, MSP_REBOOT_MSC,
)


class TestMspFraming(unittest.TestCase):
    def test_reboot_to_mass_storage_frame(self):
        frame = encode_msp(MSP_REBOOT, bytes([MSP_REBOOT_MSC]))
        # $M > <size=1> <cmd=0x44> <payload=0x02> <checksum>
        self.assertEqual(frame, b"$M>\x01D\x02G")

    def test_checksum(self):
        self.assertEqual(checksum(1, 0x44, 0x02), 0x47)

    def test_decode_roundtrip(self):
        payload = b"\x01\x02\x03"
        cmd = 5
        frame = (
            b"$M<"
            + bytes([len(payload)])
            + bytes([cmd])
            + payload
            + bytes([checksum(len(payload), cmd, *payload)])
        )
        self.assertEqual(decode_msp(frame), (cmd, payload))

    def test_decode_incomplete(self):
        self.assertIsNone(decode_msp(b"$M<\x02"))

    def test_decode_ignores_leading_garbage(self):
        payload = b"\x01"
        cmd = 5
        frame = b"\x00\x00$M<" + bytes([len(payload)]) + bytes([cmd]) + payload \
                + bytes([checksum(len(payload), cmd, *payload)])
        self.assertEqual(decode_msp(frame), (cmd, payload))


if __name__ == "__main__":
    unittest.main()
