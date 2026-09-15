"""
CLI schema catalog — versioned registry of Betaflight CLI schemas.

Maps a firmware version string (e.g. ``"4.5.0"``, ``"4.6.0"``) to the
closest known schema, loading JSON artifacts lazily and caching them.

New firmware versions are added by dropping a generated JSON into
``definitions/`` and registering it below — no code changes required.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fpv_tuner.core.cli.schema import CliSchema, load_schema

_DEFINITIONS_DIR = Path(__file__).parent / "definitions"

# Registry key -> JSON filename inside definitions/.
_REGISTRY = {
    "betaflight_4_5": "betaflight_4_5.json",
    "betaflight_latest": "betaflight_latest.json",
}

# Semantic-version prefix -> registry key (first match wins).
_VERSION_ROUTING = [
    ("4.5", "betaflight_4_5"),
    ("4.6", "betaflight_latest"),
    ("4.7", "betaflight_latest"),
]

DEFAULT_KEY = "betaflight_latest"

_VERSION_RE = re.compile(r"(\d+)\.(\d+)")


@lru_cache(maxsize=16)
def _load(key: str) -> CliSchema:
    if key not in _REGISTRY:
        key = DEFAULT_KEY
    path = _DEFINITIONS_DIR / _REGISTRY[key]
    return load_schema(path)


def _detect_key(version: Optional[str]) -> str:
    """Route a firmware version string to a registry key."""
    if not version:
        return DEFAULT_KEY
    m = _VERSION_RE.search(str(version))
    if not m:
        return DEFAULT_KEY
    major, minor = int(m.group(1)), int(m.group(2))
    if major < 4:
        # Pre-4.x firmware uses a completely different CLI namespace;
        # fall back to the latest so callers at least get modern names.
        return DEFAULT_KEY
    if major >= 2025:
        # CalVer (2025.x, 2026.x) maps to the latest schema
        return DEFAULT_KEY
    for prefix, key in _VERSION_ROUTING:
        pm = _VERSION_RE.match(prefix)
        if pm and major == int(pm.group(1)) and minor <= int(pm.group(2)):
            return key
    return DEFAULT_KEY


def get_schema(version: Optional[str] = None) -> CliSchema:
    """Return the closest schema for a firmware version string."""
    return _load(_detect_key(version))


def schema_for_version(version: Optional[str]) -> CliSchema:
    """Alias for get_schema — descriptive name for cross-module clarity."""
    return get_schema(version)


def list_available_schemas() -> dict:
    """Return {registry_key: CliSchema} for every bundled schema."""
    return {key: _load(key) for key in _REGISTRY}
