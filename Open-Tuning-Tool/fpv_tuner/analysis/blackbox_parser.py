"""
Blackbox header parsing.

Supports two formats:
1. ``blackbox_decode --save-headers`` output (``*.headers.csv``) — a two-column
   CSV ``fieldname, fieldvalue`` (this is what the loader now produces).
2. Legacy inline ``H field: value`` lines (kept for backwards compatibility).
"""
import csv


def _get(headers: dict, key: str, default: str = "") -> str:
    """Case-insensitive lookup of a header field."""
    for k, v in headers.items():
        if k.lower() == key.lower():
            return v
    return default


def parse_headers_csv(file_path: str) -> dict:
    """
    Parse a ``blackbox_decode --save-headers`` ``*.headers.csv`` file.

    Returns a dict of {fieldname: fieldvalue} (raw strings, original casing).
    """
    headers = {}
    try:
        with open(file_path, "r", newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2:
                    continue
                key = row[0].strip()
                value = row[1].strip()
                if key and key.lower() != "fieldname":
                    headers[key] = value
    except Exception as e:
        print(f"Could not read headers from {file_path}: {e}")
    return headers


def get_blackbox_headers(file_path):
    """
    Read blackbox headers from a decoded CSV.

    Supports the legacy inline ``H field: value`` format.  Prefer
    ``parse_headers_csv`` for ``--save-headers`` output.
    """
    headers = {}
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for _ in range(200):
                line = f.readline()
                if not line:
                    break
                stripped = line.strip()
                if stripped.startswith("H "):
                    content = stripped[2:]
                    if ":" in content:
                        key, value = content.split(":", 1)
                        headers[key.strip()] = value.strip()
    except Exception as e:
        print(f"Could not read blackbox headers from {file_path}: {e}")
    return headers


def _int(values, idx, default=0):
    try:
        return int(float(str(values[idx]).strip()))
    except (IndexError, ValueError, TypeError):
        return default


def parse_pid_data_from_headers(headers):
    """
    Extract PID values from blackbox headers.

    Reads ``rollPID``/``pitchPID``/``yawPID`` (comma-separated P,I,D) and
    ``ff_weight`` (feedforward), plus ``d_max``/``d_min`` when present.
    """
    pids = {}
    for axis in ("roll", "pitch", "yaw"):
        raw = _get(headers, f"{axis}PID")
        if not raw:
            continue
        values = raw.split(",")
        pids[f"p_{axis}"] = _int(values, 0)
        pids[f"i_{axis}"] = _int(values, 1)
        pids[f"d_{axis}"] = _int(values, 2)

    ff = _get(headers, "ff_weight")
    if ff:
        fv = ff.split(",")
        for i, axis in enumerate(("roll", "pitch", "yaw")):
            pids[f"f_{axis}"] = _int(fv, i)

    # D Max (4.6+) or D Min (4.5) — raw per-axis values.
    for prefix, out in (("d_max", "d_max"), ("d_min", "d_min")):
        raw = _get(headers, prefix)
        if raw:
            vals = raw.split(",")
            for i, axis in enumerate(("roll", "pitch", "yaw")):
                pids[f"{out}_{axis}"] = _int(vals, i)

    return pids
