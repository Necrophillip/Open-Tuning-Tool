"""
Serial transport for Betaflight flight controllers.

Pure Python, no Qt.  Provides:

- ``ports``      — cross-platform serial port discovery
- ``connection`` — SerialConnection with timeouts / context manager
- ``msp``        — MSP framing and a minimal client (version, reboot)
- ``cli``        — text CLI session + apply changes to the FC
- ``msc``        — mass-storage mode + .BBL extraction
"""
from fpv_tuner.core.serial.ports import SerialPortInfo, SerialPortError, list_serial_ports
from fpv_tuner.core.serial.connection import SerialConnection, SerialConnectionError
from fpv_tuner.core.serial.msp import MspClient, MspError, encode_msp, decode_msp, MSP_REBOOT_MSC
from fpv_tuner.core.serial.cli import CliSession, CliSessionError, WriteResult, write_changes_to_fc

__all__ = [
    "SerialPortInfo",
    "SerialPortError",
    "list_serial_ports",
    "SerialConnection",
    "SerialConnectionError",
    "MspClient",
    "MspError",
    "encode_msp",
    "decode_msp",
    "MSP_REBOOT_MSC",
    "CliSession",
    "CliSessionError",
    "WriteResult",
    "write_changes_to_fc",
]
