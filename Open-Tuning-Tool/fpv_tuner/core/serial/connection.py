"""
Serial connection — thin wrapper around pyserial with strict timeouts.

Pure Python, no Qt.  Implements a context manager, buffer flushing,
line/pattern reads with timeouts, and clear error reporting so the UI
never blocks indefinitely on a dead or disconnected port.
"""
from __future__ import annotations

import time
import logging
from typing import Optional

import serial
from serial.serialutil import SerialException

logger = logging.getLogger(__name__)


class SerialConnectionError(RuntimeError):
    """Raised on open/read/write failures with a user-facing message."""


class SerialConnection:
    """
    A single serial link to the flight controller.

    Usage::

        with SerialConnection("/dev/tty.usbmodem1234") as conn:
            conn.write(b"#")
            conn.read_until(b"#", timeout=3.0)
    """

    def __init__(self, port: str, baudrate: int = 115200,
                 timeout: float = 1.0, write_timeout: float = 2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self._serial: Optional[serial.Serial] = None

    # ── Lifecycle ─────────────────────────────────────────────────

    def open(self) -> "SerialConnection":
        if self._serial and self._serial.is_open:
            return self
        logger.info("Opening serial port %s @ %d baud", self.port, self.baudrate)
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.write_timeout,
            )
        except (SerialException, OSError, ValueError) as exc:
            logger.error("Failed to open %s: %s", self.port, exc)
            raise SerialConnectionError(
                f"Could not open serial port '{self.port}': {exc}"
            ) from exc
        logger.info("Serial port %s opened", self.port)
        return self

    def close(self) -> None:
        if self._serial is not None:
            logger.info("Closing serial port %s", self.port)
            try:
                if self._serial.is_open:
                    self._serial.close()
            except (SerialException, OSError):
                pass
            finally:
                self._serial = None

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def __enter__(self) -> "SerialConnection":
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ── I/O primitives ────────────────────────────────────────────

    def _require_open(self) -> serial.Serial:
        if not self.is_open:
            self.open()
        return self._serial

    def write(self, data) -> int:
        if isinstance(data, str):
            data = data.encode("utf-8")
        logger.debug("TX (%d bytes): %r", len(data), data)
        try:
            return self._require_open().write(data)
        except (SerialException, OSError) as exc:
            raise SerialConnectionError(f"Serial write failed on '{self.port}': {exc}") from exc

    def flush(self) -> None:
        try:
            self._require_open().reset_input_buffer()
            self._require_open().reset_output_buffer()
        except (SerialException, OSError):
            pass

    def read(self, n: int) -> bytes:
        try:
            data = self._require_open().read(n)
        except (SerialException, OSError) as exc:
            raise SerialConnectionError(f"Serial read failed on '{self.port}': {exc}") from exc
        if not data:
            raise SerialConnectionError(f"Serial read timed out on '{self.port}'")
        return data

    def read_available(self, timeout: float = 0.1) -> bytes:
        """Read whatever bytes are currently buffered (non-blocking)."""
        try:
            ser = self._require_open()
            ser.timeout = timeout
            return ser.read(ser.in_waiting or 1)
        except (SerialException, OSError) as exc:
            raise SerialConnectionError(f"Serial read failed on '{self.port}': {exc}") from exc

    def read_until(self, terminator, timeout: Optional[float] = None) -> bytes:
        """
        Read until ``terminator`` (bytes/str) is seen or the timeout elapses.

        Returns the accumulated bytes (terminator included when matched).
        Raises SerialConnectionError if the terminator never appears.
        """
        if isinstance(terminator, str):
            terminator = terminator.encode("utf-8")
        deadline = time.monotonic() + (timeout if timeout is not None else self.timeout)
        buf = bytearray()
        try:
            ser = self._require_open()
            while time.monotonic() < deadline:
                chunk = ser.read(1)
                if chunk:
                    buf.extend(chunk)
                    if buf.endswith(terminator):
                        logger.debug("RX (%d bytes): %r", len(buf), bytes(buf))
                        return bytes(buf)
            raise SerialConnectionError(
                f"Serial read_until timed out on '{self.port}' "
                f"(waited for {terminator!r})"
            )
        except (SerialException, OSError) as exc:
            raise SerialConnectionError(f"Serial read failed on '{self.port}': {exc}") from exc
