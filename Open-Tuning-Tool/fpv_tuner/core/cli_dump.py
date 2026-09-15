"""
Betaflight CLI dump parser and generator.

Pure Python — no Qt imports. This module will be reused as-is
by the future web backend.

Supports the `dump` command output format from Betaflight 4.5:
    # Betaflight / STM32F405 (S405) 4.5.0 ...
    set gyro_lowpass_hz = 250
    set p_pitch = 47
    ...
"""
import re
from dataclasses import dataclass, field


@dataclass
class CliDumpData:
    """Structured representation of a Betaflight CLI dump."""
    raw_text: str = ""
    version: str = ""                       # e.g. "4.5.0"
    board: str = ""                         # e.g. "STM32F405"
    target: str = ""                        # e.g. "S405"
    board_name: str = ""                    # e.g. "SPEEDYBEEF405AIO"
    manufacturer_id: str = ""               # e.g. "SPBE"
    settings: dict = field(default_factory=dict)   # set name -> value (str)
    profiles: list = field(default_factory=list)   # per-profile set blocks
    errors: list = field(default_factory=list)


# ── Parsing ───────────────────────────────────────────────────────

_VERSION_RE = re.compile(
    r"#\s*Betaflight\s*/\s*(\S+)\s*\((\S+)\)\s*([\d.]+)", re.IGNORECASE
)
_SET_RE = re.compile(r"^set\s+(\S+)\s*=\s*(.*)$", re.IGNORECASE)
_BOARD_NAME_RE = re.compile(r"^board_name\s+(\S+)", re.IGNORECASE)
_MANUFACTURER_RE = re.compile(r"^manufacturer_id\s+(\S+)", re.IGNORECASE)


def parse_dump(text: str) -> CliDumpData:
    """
    Parse raw `dump` output from the Betaflight CLI.

    Args:
        text: Full text of the dump (may include comments, profile blocks...).

    Returns:
        CliDumpData with all `set` commands extracted.
    """
    data = CliDumpData(raw_text=text)

    # Version header: "# Betaflight / STM32F405 (S405) 4.5.0 Jun 1 2024 ..."
    m = _VERSION_RE.search(text)
    if m:
        data.board = m.group(1)
        data.target = m.group(2)
        data.version = m.group(3)
    else:
        data.errors.append(
            "Could not find a Betaflight version header. "
            "Make sure you pasted the full output of the `dump` command."
        )

    # Extract all "set name = value" lines
    for line in text.splitlines():
        line = line.strip()
        m = _SET_RE.match(line)
        if m:
            name = m.group(1).lower()
            value = m.group(2).strip()
            data.settings[name] = value
            continue
        m = _BOARD_NAME_RE.match(line)
        if m:
            data.board_name = m.group(1)
            continue
        m = _MANUFACTURER_RE.match(line)
        if m:
            data.manufacturer_id = m.group(1)

    if not data.settings:
        data.errors.append("No `set` commands found in the dump.")

    return data


def load_dump_file(file_path: str) -> CliDumpData:
    """Read and parse a CLI dump from a text file."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        return parse_dump(fh.read())


# ── Generation ────────────────────────────────────────────────────

def apply_changes(dump: CliDumpData, changes: dict) -> str:
    """
    Produce a NEW dump string with the given settings changed.

    Args:
        dump:    Parsed original dump.
        changes: {setting_name: new_value} — names are case-insensitive.

    Returns:
        Complete dump text ready to paste into the CLI.
        Settings not present in the original are appended at the end.
    """
    changes_lower = {k.lower(): str(v) for k, v in changes.items()}
    output_lines = []
    applied = set()

    for line in dump.raw_text.splitlines():
        stripped = line.strip()
        m = _SET_RE.match(stripped)
        if m:
            name = m.group(1).lower()
            if name in changes_lower:
                output_lines.append(f"set {m.group(1)} = {changes_lower[name]}")
                applied.add(name)
                continue
        output_lines.append(line)

    # Append settings that didn't exist in the original dump
    missing = set(changes_lower) - applied
    if missing:
        output_lines.append("")
        output_lines.append("# ── Added by FPV Tuner ──")
        for name in sorted(missing):
            output_lines.append(f"set {name} = {changes_lower[name]}")

    return "\n".join(output_lines)
