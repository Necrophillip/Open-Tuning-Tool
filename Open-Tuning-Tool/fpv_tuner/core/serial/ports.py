"""
Serial port discovery — pure Python, no Qt.

Uses pyserial's list_ports to enumerate available serial devices in a
cross-platform way.  Gracefully degrades when pyserial is missing.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class SerialPortInfo:
    """One available serial device."""
    device: str
    description: str = ""
    hwid: str = ""
    vid: Optional[int] = None
    pid: Optional[int] = None

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def label(self) -> str:
        """Human-friendly single-line label for UI display."""
        if self.description and self.description != "n/a":
            return f"{self.device} — {self.description}"
        return self.device


class SerialPortError(RuntimeError):
    """Raised when port enumeration is unavailable."""


def list_serial_ports() -> list[SerialPortInfo]:
    """
    Return the list of currently available serial ports.

    Returns an empty list (without raising) if pyserial is unavailable.
    """
    try:
        from serial.tools import list_ports
    except ImportError:
        return []

    result = []
    try:
        comports = list_ports.comports()
    except Exception:
        return []

    for p in comports:
        result.append(SerialPortInfo(
            device=p.device,
            description=p.description or "",
            hwid=p.hwid or "",
            vid=getattr(p, "vid", None),
            pid=getattr(p, "pid", None),
        ))
    return result
