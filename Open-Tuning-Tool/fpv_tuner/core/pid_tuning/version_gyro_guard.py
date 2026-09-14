"""
version_gyro_guard — builds the TuningContext and applies hard safety gates.

Runs *before* any analyser.  Reads the blackbox headers (log-time settings),
an optional live gyro model (from CLI ``status``), and the CLI schema, then:

- extracts firmware version / board / device uid
- checks the firmware version against a team-maintained whitelist
- gates gyros that changed interpretation across versions (e.g. 42652)
- detects simplified-tuning sliders (Karate approach)
- detects the TPA model (classic ≤4.5, curve ≥4.6)
- detects chirp logs (never process them)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from fpv_tuner.core.cli.schema import CliSchema
from fpv_tuner.core.pid_tuning.tuning_context import (
    TuningContext,
    FLAG_VERSION_MISMATCH,
    FLAG_GYRO_UNKNOWN_CONSERVATIVE,
    FLAG_CHIRP_UNSUPPORTED,
)

_CONFIG_PATH = Path(__file__).parent / "version_whitelist.json"

_FW_RE = re.compile(r"Betaflight\s+([\w.\-]+)", re.IGNORECASE)
_GYRO_RE = re.compile(r"Gyro:\s*([A-Za-z0-9\-]+)")


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _version_tuple(version: str) -> tuple:
    """Parse '4.5.0' or '2026.6.1' into a comparable tuple."""
    parts = []
    for seg in version.replace("-", ".").split("."):
        try:
            parts.append(int(seg))
        except ValueError:
            break
    return tuple(parts) if parts else (0,)


def _header_get(headers: dict, *keys: str, default: str = "") -> str:
    for k, v in headers.items():
        if k.lower() in keys:
            return str(v)
    return default


def extract_firmware_version(headers: dict) -> str:
    """Return the firmware version string from the blackbox headers."""
    revision = _header_get(headers, "firmware revision")
    m = _FW_RE.search(revision)
    return m.group(1) if m else ""


def extract_board(headers: dict) -> tuple[str, str]:
    """Return (board_name, manufacturer_id) from headers."""
    info = _header_get(headers, "board information")
    parts = info.split()
    if len(parts) >= 2:
        return parts[1], parts[0]
    if parts:
        return parts[0], ""
    return "", ""


def parse_status_gyro(text: str) -> Optional[str]:
    """Extract the gyro model from CLI ``status`` output (e.g. ICM42688P)."""
    m = _GYRO_RE.search(text)
    return m.group(1) if m else None


def build_tuning_context(
    headers: dict,
    gyro_model: Optional[str] = None,
    schema: Optional[CliSchema] = None,
    config: Optional[dict] = None,
) -> TuningContext:
    """
    Build a TuningContext from blackbox headers (+ optional live gyro model).

    ``headers`` is the dict from ``parse_headers_csv`` (log-time settings).
    """
    cfg = config if config is not None else _load_config()

    firmware_version = extract_firmware_version(headers)
    board, manufacturer = extract_board(headers)
    device_uid = _header_get(headers, "deviceuid")
    debug_mode = _header_get(headers, "debug_mode")

    ctx = TuningContext(
        firmware_version=firmware_version,
        board=board,
        manufacturer_id=manufacturer,
        device_uid=device_uid,
        gyro_model=gyro_model,
        schema=schema,
    )

    # ── Version whitelist ─────────────────────────────────────────
    prefixes = cfg.get("supported_version_prefixes", [])
    ctx.version_supported = bool(prefixes) and any(
        firmware_version.startswith(p) for p in prefixes
    ) if firmware_version else False
    if not ctx.version_supported:
        ctx.warnings.append(FLAG_VERSION_MISMATCH)

    # ── Gyro gate (changed interpretation across versions) ────────
    gyro_gate = cfg.get("gyro_version_gate", {})
    if gyro_model:
        for marker, min_version in gyro_gate.items():
            if marker.lower() in gyro_model.lower():
                if not firmware_version or _version_tuple(firmware_version) < _version_tuple(min_version):
                    ctx.warnings.append(FLAG_GYRO_UNKNOWN_CONSERVATIVE)
                    ctx.warnings.append(FLAG_VERSION_MISMATCH)
                    break
    else:
        # No live status -> we do not know the gyro. Conservative mode.
        ctx.gyro_model_unknown = True
        ctx.warnings.append(FLAG_GYRO_UNKNOWN_CONSERVATIVE)

    # ── Simplified tuning sliders detection ───────────────────────
    ctx.uses_simplified_sliders = _detect_simplified_sliders(headers)

    # ── TPA model (by schema presence) ────────────────────────────
    if schema is not None and "tpa_curve_type" in schema:
        ctx.tpa_model = "curve"
    else:
        ctx.tpa_model = "classic"

    # ── Chirp detection ───────────────────────────────────────────
    ctx.chirp_detected = _detect_chirp(headers, debug_mode, cfg)

    return ctx


def _detect_simplified_sliders(headers: dict) -> bool:
    """True if the profile uses the simplified-tuning slider (Karate) approach."""
    mode = _header_get(headers, "simplified_pids_mode")
    dterm = _header_get(headers, "simplified_dterm_filter")
    gyro = _header_get(headers, "simplified_gyro_filter")
    # Any of the master toggles being non-off/on indicates sliders are active.
    if mode and mode not in ("0", "OFF"):
        return True
    if dterm and dterm not in ("0", "OFF"):
        return True
    if gyro and gyro not in ("0", "OFF"):
        return True
    return False


def _detect_chirp(headers: dict, debug_mode: str, cfg: dict) -> bool:
    """Detect a chirp log (must never be processed by this module)."""
    chirp_capable = any("chirp" in k.lower() for k in headers)
    if not chirp_capable:
        return False
    chirp_values = {str(v) for v in cfg.get("debug_mode_chirp_values", [])}
    if debug_mode and debug_mode in chirp_values:
        return True
    return False
