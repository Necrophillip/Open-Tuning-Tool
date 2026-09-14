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
from fpv_tuner.core.serial.cli import CliSession, CliSessionError, WriteResult, write_changes_to_fc, read_dump, read_status
from fpv_tuner.core.serial.autodetect import is_flight_controller, detect_flight_controller
from fpv_tuner.core.serial.msc import (
    MassStorageError,
    find_mount_points,
    wait_for_mount,
    locate_bbl_files,
    copy_bbl_files,
    copy_blackbox_file,
    filter_blackbox_files,
    enter_and_list_blackbox,
    eject,
    enter_mass_storage,
    extract_bbl,
)

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
    "read_dump",
    "read_status",
    "is_flight_controller",
    "detect_flight_controller",
    "MassStorageError",
    "find_mount_points",
    "wait_for_mount",
    "locate_bbl_files",
    "copy_bbl_files",
    "copy_blackbox_file",
    "filter_blackbox_files",
    "enter_and_list_blackbox",
    "eject",
    "enter_mass_storage",
    "extract_bbl",
]
