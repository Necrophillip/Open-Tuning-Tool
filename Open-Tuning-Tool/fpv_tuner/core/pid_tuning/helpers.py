"""
Shared helpers for reading blackbox headers and clamping values.
"""
from __future__ import annotations

from typing import Optional


def hget(headers: dict, key: str, default: str = "") -> str:
    """Case-insensitive header lookup."""
    for k, v in headers.items():
        if k.lower() == key.lower():
            return str(v)
    return default


def parse_int(value, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return default


def parse_int_list(value) -> list[int]:
    """Parse a comma-separated list like '100,80,0' into ints."""
    if not value:
        return []
    out = []
    for part in str(value).split(","):
        try:
            out.append(int(float(part.strip())))
        except ValueError:
            out.append(0)
    return out


def clamp_int(value: int, lo: Optional[int] = None, hi: Optional[int] = None) -> int:
    if lo is not None and value < lo:
        value = lo
    if hi is not None and value > hi:
        value = hi
    return value
