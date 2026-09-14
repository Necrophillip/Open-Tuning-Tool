"""
Betaflight CLI session over serial + write changes to the FC.

Pure Python, no Qt.  Implements the text-based Betaflight CLI protocol:
enter CLI with ``#``, run commands line-by-line, and save.

``write_changes_to_fc`` is the high-level entry point used by the UI to
apply recommended settings directly to a connected flight controller.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from fpv_tuner.core.serial.connection import SerialConnection, SerialConnectionError
from fpv_tuner.core.cli.schema import CliSchema
from fpv_tuner.core.cli.validator import validate_change, normalize_name

logger = logging.getLogger(__name__)


class CliSessionError(RuntimeError):
    """Raised on CLI protocol / command failures."""


@dataclass
class WriteResult:
    """Outcome of applying changes to the FC."""
    success: bool = False
    applied: list[str] = field(default_factory=list)      # settings applied
    errors: list[str] = field(default_factory=list)       # validation/IO errors
    raw_log: list[str] = field(default_factory=list)      # raw CLI responses

    @property
    def n_applied(self) -> int:
        return len(self.applied)


class CliSession:
    """
    A text CLI session over an open SerialConnection.

    Usage::

        with SerialConnection(port) as conn:
            cli = CliSession(conn)
            cli.enter()
            cli.set("p_roll", "47")
            cli.save()
    """

    CLI_PROMPT = "#"

    def __init__(self, connection: SerialConnection,
                 enter_timeout: float = 3.0, command_timeout: float = 3.0):
        self.conn = connection
        self.enter_timeout = enter_timeout
        self.command_timeout = command_timeout
        self._entered = False

    # ── Low-level reads ───────────────────────────────────────────

    def _read_to_prompt(self, timeout: float) -> str:
        """Read until the CLI ``#`` prompt appears, returning the text."""
        buf = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                chunk = self.conn.read_available(timeout=0.1)
            except SerialConnectionError:
                chunk = b""
            if chunk:
                buf.extend(chunk)
            text = buf.decode("utf-8", errors="replace")
            if self._has_prompt(text):
                return text
        raise CliSessionError("CLI did not respond with a prompt (timeout)")

    @staticmethod
    def _has_prompt(text: str) -> bool:
        # Prompt is a bare '#' at the start of the current line.
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            if line.strip() == "#":
                return True
        return False

    # ── Session control ───────────────────────────────────────────

    def enter(self) -> str:
        """Enter CLI mode and return the banner text."""
        logger.info("Entering CLI mode on %s", self.conn.port)
        self.conn.flush()
        # Allow the FC a moment to settle after (re)opening the port — an
        # immediately preceding MSP session can leave it briefly unready.
        time.sleep(0.3)
        self.conn.write(b"#")
        banner = None
        for attempt in range(3):
            try:
                banner = self._read_to_prompt(self.enter_timeout)
                break
            except CliSessionError:
                logger.warning("No CLI prompt after '#' (attempt %d); retrying", attempt + 1)
                time.sleep(0.5)
                self.conn.write(b"#")  # some firmwares need a second '#'
        else:
            raise CliSessionError("Could not enter CLI mode — is the port connected to a Betaflight FC?")

        self._entered = True
        logger.info("CLI banner: %r", banner[:120] if banner else "")

        # Betaflight swallows the *first* command after entering CLI mode
        # (it is echoed but never executed). Send a blank line to absorb it
        # so the first real command is not silently lost.
        logger.debug("Sending warm-up blank line")
        self.conn.write(b"\n")
        try:
            self._read_to_prompt(self.enter_timeout)
        except CliSessionError:
            pass

        return banner

    def _command(self, cmd: str) -> str:
        if not self._entered:
            raise CliSessionError("Not in CLI mode — call enter() first")
        logger.info("CLI >> %s", cmd)
        self.conn.write((cmd + "\n").encode("utf-8"))
        resp = self._read_to_prompt(self.command_timeout)
        logger.info("CLI << %r", resp)
        return resp

    def get(self, name: str) -> str:
        return self._command(f"get {name}")

    def set(self, name: str, value) -> str:
        return self._command(f"set {name} = {value}")

    def save(self) -> str:
        return self._command("save")

    def dump(self) -> str:
        return self._command("dump")

    def exit(self) -> None:
        try:
            self.conn.write(b"exit\n")
        except (SerialConnectionError, OSError):
            pass
        self._entered = False


def _normalize_changes(changes) -> list[tuple[str, str]]:
    """
    Accept changes as a dict, a list of (name, value) tuples, a CliDiff,
    or a Prescription, and return a normalized list of (name, value).
    """
    if isinstance(changes, dict):
        return [(str(k), str(v)) for k, v in changes.items()]
    pairs = []
    for item in changes:
        if isinstance(item, (tuple, list)) and len(item) == 2:
            pairs.append((str(item[0]), str(item[1])))
        elif hasattr(item, "setting") and hasattr(item, "new_value"):
            pairs.append((str(item.setting), str(item.new_value)))
        else:
            raise CliSessionError(f"Unsupported change entry: {item!r}")
    return pairs


def write_changes_to_fc(
    port: str,
    changes,
    schema: Optional[CliSchema] = None,
    profile: int = 0,
    rateprofile: int = 0,
    baudrate: int = 115200,
    save: bool = True,
) -> WriteResult:
    """
    Validate ``changes`` against the schema and apply them to the FC over
    the Betaflight CLI.

    Args:
        port:       Serial device path (e.g. ``/dev/tty.usbmodem1234``).
        changes:    dict {name: value} | list[(name, value)] | CliDiff | Prescription.
        schema:     CliSchema for validation (defaults to latest).
        profile:    Profile index to select for profile-scoped settings.
        rateprofile: Rate-profile index for rateprofile-scoped settings.
        baudrate:   Serial baudrate (default 115200).
        save:       Whether to issue ``save`` at the end.

    Returns:
        WriteResult describing what was applied and any errors.
    """
    if schema is None:
        from fpv_tuner.core.cli import get_schema
        schema = get_schema(None)

    logger.info("write_changes_to_fc: port=%s schema=%s changes=%d", port, schema.version, len(changes) if not isinstance(changes, dict) else len(changes))

    result = WriteResult()
    pairs = _normalize_changes(changes)

    # Validate everything up front; fail fast on unknown names.
    plan: list[tuple[str, str]] = []
    for name, value in pairs:
        try:
            canonical = normalize_name(schema, name)
            problems = validate_change(schema, canonical, value)
        except Exception as exc:
            logger.warning("Rejected %s: %s", name, exc)
            result.errors.append(str(exc))
            continue
        if problems:
            logger.warning("Rejected %s=%s: %s", name, value, "; ".join(problems))
            result.errors.append(f"{name}: {'; '.join(problems)}")
            continue
        plan.append((canonical, value))

    if result.errors:
        logger.error("Validation failed; aborting write: %s", result.errors)
        result.success = False
        return result

    # Order: selectors must precede their scoped settings.
    ordered = []
    master = [p for p in plan if _scope(schema, p[0]) == "master"]
    prof = [p for p in plan if _scope(schema, p[0]) == "profile"]
    rate = [p for p in plan if _scope(schema, p[0]) == "rateprofile"]
    other = [p for p in plan if _scope(schema, p[0]) not in ("master", "profile", "rateprofile")]

    if prof:
        ordered.append(("__profile__", str(profile)))
        ordered.extend(prof)
    ordered.extend(master + other)
    if rate:
        ordered.append(("__rateprofile__", str(rateprofile)))
        ordered.extend(rate)

    try:
        with SerialConnection(port, baudrate=baudrate) as conn:
            cli = CliSession(conn)
            result.raw_log.append(cli.enter())

            for name, value in ordered:
                if name == "__profile__":
                    result.raw_log.append(cli._command(f"profile {value}"))
                elif name == "__rateprofile__":
                    result.raw_log.append(cli._command(f"rateprofile {value}"))
                else:
                    resp = cli.set(name, value)
                    result.raw_log.append(resp)
                    result.applied.append(f"{name} = {value}")

            if save:
                logger.info("Saving and rebooting the FC")
                result.raw_log.append(cli.save())
    except (CliSessionError, SerialConnectionError) as exc:
        logger.error("Write failed: %s", exc)
        result.errors.append(str(exc))
        result.success = False
        return result

    logger.info("Write complete: %d setting(s) applied", result.n_applied)
    result.success = True
    return result


def _scope(schema: CliSchema, name: str) -> str:
    var = schema.get(name)
    return var.scope if var is not None else "master"


def read_dump(
    port: str,
    baudrate: int = 115200,
    enter_timeout: float = 3.0,
    dump_timeout: float = 15.0,
    retries: int = 2,
):
    """
    Connect to the FC, enter the CLI, and read the full ``dump`` output.

    Returns a ``CliDumpData`` (parsed settings + firmware version), reusing
    the parser in ``fpv_tuner.core.cli_dump``.  Retries once or twice if the
    dump comes back empty (a freshly-rebooted FC can drop the first read).
    """
    from fpv_tuner.core.cli_dump import parse_dump

    data = None
    for attempt in range(retries + 1):
        logger.info("read_dump: port=%s (attempt %d)", port, attempt + 1)
        with SerialConnection(port, baudrate=baudrate) as conn:
            cli = CliSession(conn, enter_timeout=enter_timeout, command_timeout=dump_timeout)
            cli.enter()
            try:
                raw = cli.dump()
            finally:
                cli.exit()
        data = parse_dump(raw)
        if data.settings:
            break
        logger.warning("read_dump: empty/truncated dump (attempt %d); retrying", attempt + 1)
        time.sleep(1.0)

    logger.info("read_dump: parsed %d settings, version=%s", len(data.settings), data.version)
    return data


def read_status(
    port: str,
    baudrate: int = 115200,
    enter_timeout: float = 3.0,
    status_timeout: float = 5.0,
) -> str:
    """
    Connect to the FC, enter the CLI, and run ``status``.

    Returns the raw ``status`` output (used to extract the gyro model and
    other live hardware info).
    """
    logger.info("read_status: port=%s", port)
    with SerialConnection(port, baudrate=baudrate) as conn:
        cli = CliSession(conn, enter_timeout=enter_timeout, command_timeout=status_timeout)
        cli.enter()
        try:
            raw = cli._command("status")
        finally:
            cli.exit()
    return raw
