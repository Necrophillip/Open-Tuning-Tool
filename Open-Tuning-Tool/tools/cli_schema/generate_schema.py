#!/usr/bin/env python3
"""
Generate a versioned Betaflight CLI schema (JSON) from the firmware source.

The authoritative source of truth for Betaflight CLI variables is
``src/main/cli/settings.c`` (with the string names of the ``PARAM_NAME_*``
macros resolved from ``src/main/fc/parameter_names.h``).

This script:

1. Downloads (or reads from disk) those two files for a given ref/tag.
2. Parses every ``{ ... }`` variable entry (name, type, scope, min/max).
3. Resolves the numeric constants used in min/max via a curated map.
4. Emits a JSON artifact consumed by ``fpv_tuner.core.cli``.

Usage::

    python3 tools/cli_schema/generate_schema.py \
        --ref 4.5-maintenance --version 4.5.0 \
        --out fpv_tuner/core/cli/definitions/betaflight_4_5.json

    python3 tools/cli_schema/generate_schema.py \
        --ref master --version 4.6.0 \
        --out fpv_tuner/core/cli/definitions/betaflight_latest.json
"""
import argparse
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

RAW_BASE = "https://raw.githubusercontent.com/betaflight/betaflight/{ref}/src/main"

# Value-type → python-ish datatype label.
TYPE_MAP = {
    "VAR_UINT8": "uint8",
    "VAR_UINT16": "uint16",
    "VAR_UINT32": "uint32",
    "VAR_INT8": "int8",
    "VAR_INT16": "int16",
    "VAR_INT32": "int32",
}

SCOPE_FLAGS = {
    "MASTER_VALUE": "master",
    "PROFILE_VALUE": "profile",
    "PROFILE_RATE_VALUE": "rateprofile",
    "HARDWARE_VALUE": "hardware",
}

# Curated resolution of the C constants that appear inside minmax ranges.
# Kept small on purpose: unknown constants are left as ``null`` so the
# schema never lies about a range it could not resolve.
CONSTANTS = {
    "UINT8_MAX": 255,
    "UINT16_MAX": 65535,
    "UINT32_MAX": 4294967295,
    "INT8_MAX": 127,
    "INT8_MIN": -128,
    "INT16_MAX": 32767,
    "INT16_MIN": -32768,
    "INT32_MAX": 2147483647,
    "INT32_MIN": -2147483648,
    "LPF_MAX_HZ": 1000,
    "DYN_LPF_MAX_HZ": 1000,
    "DYN_NOTCH_COUNT_MAX": 5,
    "PID_GAIN_MAX": 250,
    "F_GAIN_MAX": 1000,
    "PIDSUM_LIMIT_MIN": 100,
    "PIDSUM_LIMIT_MAX": 1000,
    "PWM_RANGE_MIN": 750,
    "PWM_RANGE_MAX": 2250,
    "PWM_RANGE_MIDDLE": 1500,
    "PWM_PULSE_MIN": 750,
    "PWM_PULSE_MAX": 2250,
}

# Enum tables used by MODE_LOOKUP entries (subset we care about).
ENUM_TABLES = {
    "TABLE_OFF_ON": ["OFF", "ON"],
    "TABLE_GYRO_LPF_TYPE": ["PT1", "PT2", "PT3", "BIQUAD", "PT1FIXED2K"],
    "TABLE_DTERM_LPF_TYPE": ["PT1", "PT2", "PT3", "BIQUAD", "PT1FIXED2K"],
}

_NAME_DEF_RE = re.compile(r'#define\s+(PARAM_NAME_\w+)\s+"([^"]+)"')
_ENTRY_LINE_RE = re.compile(
    r"^\s*\{\s*(?P<name>\"[^\"]+\"|PARAM_NAME_\w+)\s*,\s*(?P<type>VAR_[A-Z0-9]+)"
    r"(?:\s*\|\s*(?P<flags>[A-Z0-9_| ]+?))?\s*,\s*(?P<rest>.*)\}\s*,?\s*$"
)
_MINMAX_RE = re.compile(r"minmax(?:Unsigned)?\s*=\s*\{\s*([^,}]+)\s*,\s*([^}]+)\s*\}")
_LOOKUP_RE = re.compile(r"lookup\s*=\s*\{\s*(\w+)\s*\}")


def _fetch(ref: str, path: str) -> str:
    url = RAW_BASE.format(ref=ref) + "/" + path
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _resolve_const(token: str):
    token = token.strip()
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    if token.startswith("(") and token.endswith(")"):
        inner = token[1:-1].strip()
        return _resolve_const(inner)
    return CONSTANTS.get(token)


def _parse_names(text: str) -> dict:
    return {m.group(1): m.group(2) for m in _NAME_DEF_RE.finditer(text)}


def _scope(flags: str) -> str:
    for flag, scope in SCOPE_FLAGS.items():
        if flag in flags:
            return scope
    return "master"


def _parse_entry(name_token: str, type_token: str, flags: str, config: str, names: dict):
    if name_token.startswith("PARAM_NAME_"):
        name = names.get(name_token)
        if name is None:
            return None
    else:
        name = name_token.strip('"')

    var_type = type_token.strip()
    datatype = TYPE_MAP.get(var_type, var_type.lower())
    is_array = "MODE_ARRAY" in flags

    entry = {
        "name": name,
        "type": var_type,
        "datatype": datatype,
        "scope": _scope(flags),
        "min": None,
        "max": None,
        "enum_table": None,
        "enum_values": None,
        "is_array": is_array,
    }

    mm = _MINMAX_RE.search(config)
    if mm:
        lo = _resolve_const(mm.group(1))
        hi = _resolve_const(mm.group(2))
        if lo is not None and hi is not None:
            entry["min"] = min(lo, hi)
            entry["max"] = max(lo, hi)

    lk = _LOOKUP_RE.search(config)
    if lk:
        table = lk.group(1)
        entry["enum_table"] = table
        entry["enum_values"] = ENUM_TABLES.get(table)

    return entry


def _parse_settings(text: str, names: dict) -> list:
    entries = []
    for line in text.splitlines():
        m = _ENTRY_LINE_RE.match(line)
        if not m:
            continue
        flags = (m.group("flags") or "").strip()
        entry = _parse_entry(
            m.group("name"), m.group("type"), flags, m.group("rest"), names
        )
        if entry:
            entries.append(entry)

    seen = {}
    for e in entries:
        seen[e["name"]] = e
    return list(seen.values())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", default="master",
                        help="Git ref/tag of betaflight/betaflight to fetch.")
    parser.add_argument("--version", required=True, help="Firmware version label (e.g. 4.5.0).")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    parser.add_argument("--settings", help="Path to a local settings.c (skip download).")
    parser.add_argument("--names", help="Path to a local parameter_names.h (skip download).")
    parser.add_argument("--firmware", default="betaflight")
    args = parser.parse_args(argv)

    if args.settings:
        settings_text = _read(args.settings)
    else:
        settings_text = _fetch(args.ref, "cli/settings.c")

    if args.names:
        names_text = _read(args.names)
    else:
        names_text = _fetch(args.ref, "fc/parameter_names.h")

    names = _parse_names(names_text)
    variables = _parse_settings(settings_text, names)

    # Order by name for stable diffs.
    variables.sort(key=lambda e: e["name"])
    var_map = {v["name"]: v for v in variables}

    schema = {
        "firmware": args.firmware,
        "version": args.version,
        "source_ref": args.ref,
        "variables": var_map,
        "n_variables": len(variables),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(variables)} variables -> {out}")


if __name__ == "__main__":
    main()
