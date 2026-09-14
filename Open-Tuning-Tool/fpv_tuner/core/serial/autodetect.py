"""
Flight-controller auto-detection over serial.

Pure Python, no Qt.  Polls the available serial ports for a Betaflight
device (by USB VID/PID or description) and confirms it responds to MSP.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from fpv_tuner.core.serial.ports import list_serial_ports, SerialPortInfo
from fpv_tuner.core.serial.connection import SerialConnection
from fpv_tuner.core.serial.msp import MspClient

logger = logging.getLogger(__name__)

# STMicroelectronics USB vendor id (used by Betaflight VCP).
_BETAFLIGHT_VID = 0x0483
# Common Betaflight VCP product ids.
_BETAFLIGHT_PIDS = {0x5740, 0xDF11}

_DESCRIPTION_HINTS = ("betaflight", "cleanflight", "inav", "speedybee", "ardupilot")


def is_flight_controller(port: SerialPortInfo) -> bool:
    """Heuristic: does this serial port look like a flight controller?"""
    if port.vid == _BETAFLIGHT_VID and port.pid in _BETAFLIGHT_PIDS:
        return True
    desc = (port.description or "").lower()
    return any(hint in desc for hint in _DESCRIPTION_HINTS)


def detect_flight_controller(timeout: float = 30.0, interval: float = 1.0) -> Optional[str]:
    """
    Poll for a flight controller that responds to MSP.

    Args:
        timeout:  How long to keep looking (seconds).
        interval: Delay between polls (seconds).

    Returns:
        The device path of the first responsive FC, or None on timeout.
    """
    logger.info("Detecting flight controller (timeout=%.0fs)...", timeout)
    deadline = time.monotonic() + timeout
    while True:
        for port in list_serial_ports():
            if not is_flight_controller(port):
                continue
            try:
                with SerialConnection(port.device, baudrate=115200) as conn:
                    MspClient(conn, timeout=1.0).api_version()
                logger.info("Flight controller detected on %s (%s)", port.device, port.description)
                return port.device
            except Exception as exc:
                logger.debug("Port %s not responding to MSP: %s", port.device, exc)
        if time.monotonic() >= deadline:
            break
        time.sleep(interval)
    logger.warning("No flight controller detected within %.0fs", timeout)
    return None
