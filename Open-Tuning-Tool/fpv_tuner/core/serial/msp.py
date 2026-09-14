"""
MSP (MultiWii Serial Protocol) framing and a minimal client.

Pure Python, no Qt.  Implements the Betaflight/MSP wire format
(``$M<dir><size><command><payload><checksum>``) plus the handful of
commands needed to identify a board and trigger a reboot into mass
storage mode.
"""
from __future__ import annotations

import logging
from typing import Optional

from fpv_tuner.core.serial.connection import SerialConnection, SerialConnectionError

logger = logging.getLogger(__name__)

MSP_PREFIX = b"$M"

# Direction bytes ('<' to the FC, '>' from the FC).
MSP_DIR_TO_FC = ord("<")
MSP_DIR_FROM_FC = ord(">")

# Command IDs (Betaflight msp_protocol.h).
MSP_API_VERSION = 1
MSP_FC_VARIANT = 2
MSP_FC_VERSION = 3
MSP_BOARD_INFO = 4
MSP_REBOOT = 68

# Reboot modes (mspRebootModes_e).
MSP_REBOOT_FIRMWARE = 0
MSP_REBOOT_BOOTLOADER = 1
MSP_REBOOT_MSC = 2
MSP_REBOOT_MSC_UTC = 3


class MspError(RuntimeError):
    """Raised on MSP framing / protocol errors."""


def checksum(*data) -> int:
    """MSP checksum is the XOR of size, command and payload bytes."""
    result = 0
    for b in data:
        result ^= b
    return result & 0xFF


def encode_msp(command: int, payload: bytes = b"") -> bytes:
    """
    Build an MSP request frame to send to the FC.

    ``$M`` ``<`` ``size`` ``command`` ``payload`` ``checksum``
    """
    size = len(payload)
    return (
        MSP_PREFIX
        + bytes([MSP_DIR_TO_FC, size, command & 0xFF])
        + payload
        + bytes([checksum(size, command & 0xFF, *payload)])
    )


def decode_msp(data: bytes) -> Optional[tuple[int, bytes]]:
    """
    Attempt to decode an MSP response frame.

    Returns ``(command, payload)`` or ``None`` if no complete frame is
    present.  ``data`` is expected to be a buffer that may contain extra
    bytes before/after the frame.
    """
    idx = data.find(MSP_PREFIX)
    if idx < 0 or idx + 5 > len(data):
        return None
    if data[idx + 2] != MSP_DIR_FROM_FC:
        return None
    size = data[idx + 3]
    command = data[idx + 4]
    end = idx + 5 + size
    if end + 1 > len(data):
        return None  # incomplete frame
    payload = data[idx + 5:end]
    expected = checksum(size, command, *payload)
    if data[end] != expected:
        raise MspError(
            f"MSP checksum mismatch (got {data[end]:#x}, expected {expected:#x})"
        )
    return command, payload


class MspClient:
    """
    High-level MSP client over a SerialConnection.
    """

    def __init__(self, connection: SerialConnection, timeout: float = 1.0):
        self.conn = connection
        self.timeout = timeout

    def _request(self, command: int, payload: bytes = b"") -> bytes:
        logger.info("MSP request command=%d payload=%r", command, payload)
        self.conn.write(encode_msp(command, payload))
        buf = bytearray()
        remaining = self.timeout
        while remaining > 0:
            try:
                chunk = self.conn.read_available(timeout=0.1)
            except SerialConnectionError:
                chunk = b""
            if chunk:
                buf.extend(chunk)
                try:
                    result = decode_msp(bytes(buf))
                except MspError:
                    raise
                if result is not None:
                    logger.info("MSP response command=%d payload=%r", result[0], result[1])
                    return result[1]
            else:
                remaining -= 0.1
        raise MspError(f"MSP command {command} timed out (no response)")

    def api_version(self) -> tuple[int, int]:
        """Return (msp protocol version, api version)."""
        payload = self._request(MSP_API_VERSION)
        if len(payload) >= 2:
            return payload[0], payload[1]
        raise MspError("Malformed MSP_API_VERSION response")

    def fc_variant(self) -> str:
        """Return the four-char flight controller variant (e.g. 'BTFL')."""
        payload = self._request(MSP_FC_VARIANT)
        return payload.decode("ascii", errors="replace").strip()

    def fc_version(self) -> str:
        """Return the firmware version string (e.g. '4.5.0')."""
        payload = self._request(MSP_FC_VERSION)
        return payload.decode("ascii", errors="replace").strip()

    def reboot(self, mode: int = MSP_REBOOT_FIRMWARE) -> None:
        """
        Send a reboot command.  The FC will not send a response for some
        modes (bootloader/MSC), so this is fire-and-forget.
        """
        logger.info("Sending MSP_REBOOT mode=%d", mode)
        self.conn.write(encode_msp(MSP_REBOOT, bytes([mode & 0xFF])))

    def reboot_to_mass_storage(self) -> None:
        """Reboot into USB mass-storage mode (exposes the flash as a drive)."""
        logger.info("Requesting reboot to mass-storage mode")
        self.reboot(MSP_REBOOT_MSC)
