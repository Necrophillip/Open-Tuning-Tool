"""
Session History — track tuning iterations per flight controller.

Pure Python, no Qt.  Persists each tuning session (log analysis +
diagnosis + prescription) to a local JSON store, keyed by flight
controller, so users can compare iterations, revert changes, and see
whether their tuning actually helped.

Storage: ~/.fpv_tuner/sessions/<fc_id>/<session_id>/snapshot.json
(falls back to a flat layout for legacy sessions without an fc_id).
"""
import json
import os
import re
import time
import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from fpv_tuner.core.diagnostics import Finding, Severity, Category
from fpv_tuner.core.prescription import Prescription, PrescribedChange


# ── Data structures ───────────────────────────────────────────────

@dataclass
class SessionSnapshot:
    """Immutable record of one tuning iteration."""
    session_id: str = ""
    timestamp: float = 0.0
    fc_id: str = ""                  # flight-controller identity (see derive_fc_id)
    log_file: str = ""               # original .bbl path
    cli_version: str = ""            # e.g. "4.5.0"
    n_rows: int = 0
    duration_s: float = 0.0
    # Key metrics
    gyro_rms: dict = field(default_factory=dict)       # {"roll": 12.3, ...}
    dterm_rms: dict = field(default_factory=dict)
    filter_reduction: dict = field(default_factory=dict)  # {"roll": 75.2, ...}
    # Findings summary
    n_critical: int = 0
    n_warning: int = 0
    n_info: int = 0
    n_good: int = 0
    findings_summary: list = field(default_factory=list)  # [title, ...]
    # Prescription
    n_changes: int = 0
    changes_summary: list = field(default_factory=list)   # ["gyro_lowpass_hz: 250→150", ...]
    # Change control
    cli_settings: dict = field(default_factory=dict)     # full settings snapshot (pre-change)
    applied_changes: list = field(default_factory=list)  # [{"setting","old","new"}, ...]
    # User notes
    user_note: str = ""


@dataclass
class ComparisonResult:
    """Result of comparing two sessions."""
    older: SessionSnapshot
    newer: SessionSnapshot
    improvements: list[str] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)


# ── Storage backend ───────────────────────────────────────────────

_DEFAULT_DIR = Path.home() / ".fpv_tuner" / "sessions"


def _get_storage_dir() -> Path:
    """Get (and create) the sessions storage directory."""
    _DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
    return _DEFAULT_DIR


def _generate_id(log_path: str, timestamp: float) -> str:
    """Short unique session ID."""
    raw = f"{log_path}:{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def derive_fc_id(board: str = "", target: str = "", board_name: str = "",
                 manufacturer_id: str = "", serial: str = "") -> str:
    """
    Derive a stable, sanitized flight-controller identity.

    Prefers the specific ``board_name`` + ``manufacturer_id``; falls back to
    ``board`` + ``target``; appends a USB ``serial`` when available.  Returns
    a lowercase, filesystem-safe token (or "unknown").
    """
    parts = []
    if board_name and manufacturer_id:
        parts = [manufacturer_id, board_name]
    elif board and target:
        parts = [board, target]
    elif board:
        parts = [board]
    if serial:
        parts.append(serial)
    if not parts:
        return "unknown"
    raw = "-".join(parts)
    return re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-") or "unknown"


# ── Public API ────────────────────────────────────────────────────

def _snapshot_dir_for(fc_id: str, session_id: str) -> Path:
    base = _get_storage_dir()
    return base / (fc_id or "unknown") / session_id


def save_session(snapshot: SessionSnapshot) -> str:
    """
    Persist a session snapshot to disk (under its fc_id).

    Returns the session ID.
    """
    if not snapshot.session_id:
        snapshot.session_id = _generate_id(snapshot.log_file, snapshot.timestamp)
    if not snapshot.timestamp:
        snapshot.timestamp = time.time()

    storage = _snapshot_dir_for(snapshot.fc_id, snapshot.session_id)
    storage.mkdir(parents=True, exist_ok=True)

    with open(storage / "snapshot.json", "w") as fh:
        json.dump(asdict(snapshot), fh, indent=2, default=str)

    return snapshot.session_id


def load_session(session_id: str, fc_id: str = "") -> Optional[SessionSnapshot]:
    """Load a session by ID (optionally scoped to an fc_id)."""
    if fc_id:
        path = _snapshot_dir_for(fc_id, session_id) / "snapshot.json"
        if path.exists():
            with open(path) as fh:
                return SessionSnapshot(**json.load(fh))
        return None
    # Search all fc_id dirs (and legacy flat layout).
    for child in _get_storage_dir().iterdir():
        snap_file = child / "snapshot.json"
        if snap_file.exists():
            try:
                data = json.loads(snap_file.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if data.get("session_id") == session_id:
                return SessionSnapshot(**data)
        elif child.is_dir():
            found = load_session(session_id, fc_id=child.name)
            if found:
                return found
    return None


def _read_snapshot(snap_file: Path) -> Optional[SessionSnapshot]:
    try:
        data = json.loads(snap_file.read_text())
        return SessionSnapshot(**data)
    except (json.JSONDecodeError, TypeError, OSError):
        return None


def list_sessions(limit: int = 50, fc_id: Optional[str] = None) -> list[SessionSnapshot]:
    """
    List recent sessions, newest first.

    With ``fc_id``, only that flight controller's sessions are returned.
    """
    storage = _get_storage_dir()
    sessions = []

    def _collect(directory: Path, scope: Optional[str]):
        for child in directory.iterdir():
            snap_file = child / "snapshot.json"
            if snap_file.exists():
                snap = _read_snapshot(snap_file)
                if snap and (scope is None or snap.fc_id == scope):
                    sessions.append(snap)
            elif child.is_dir() and scope is None:
                _collect(child, scope)

    if fc_id:
        target = storage / fc_id
        if target.exists():
            _collect(target, fc_id)
    else:
        _collect(storage, None)

    sessions.sort(key=lambda s: s.timestamp, reverse=True)
    return sessions[:limit]


def list_sessions_by_fc(fc_id: str, limit: int = 50) -> list[SessionSnapshot]:
    """List recent sessions for one flight controller."""
    return list_sessions(limit=limit, fc_id=fc_id)


def latest_session_for_fc(fc_id: str) -> Optional[SessionSnapshot]:
    """Return the most recent session for a flight controller."""
    sessions = list_sessions_by_fc(fc_id, limit=1)
    return sessions[0] if sessions else None


def delete_session(session_id: str, fc_id: str = "") -> bool:
    """Delete a session directory."""
    import shutil
    if fc_id:
        path = _snapshot_dir_for(fc_id, session_id)
    else:
        path = _get_storage_dir() / session_id
    if path.exists():
        shutil.rmtree(path)
        return True
    return False


# ── Snapshot builder ─────────────────────────────────────────────

def build_snapshot(
    log_file: str,
    findings: list[Finding],
    prescription: Optional[Prescription] = None,
    cli_version: str = "",
    n_rows: int = 0,
    duration_s: float = 0.0,
    user_note: str = "",
    fc_id: str = "",
    cli_settings: Optional[dict] = None,
) -> SessionSnapshot:
    """
    Build a SessionSnapshot from current analysis state.

    Extracts key metrics from findings for quick comparison.  ``fc_id``
    and ``cli_settings`` enable per-FC change control / reversion.
    """
    snap = SessionSnapshot(
        timestamp=time.time(),
        fc_id=fc_id,
        log_file=log_file,
        cli_version=cli_version,
        n_rows=n_rows,
        duration_s=duration_s,
        user_note=user_note,
        cli_settings=dict(cli_settings or {}),
    )

    # Count by severity
    for f in findings:
        if f.severity == Severity.CRITICAL:
            snap.n_critical += 1
        elif f.severity == Severity.WARNING:
            snap.n_warning += 1
        elif f.severity == Severity.INFO:
            snap.n_info += 1
        else:
            snap.n_good += 1
        snap.findings_summary.append(f.title)

        # Extract metrics
        if f.category == Category.GYRO_NOISE and "rms" in f.data:
            snap.gyro_rms[f.data.get("axis_name", "?")] = f.data["rms"]
        elif f.category == Category.DTERM_NOISE and "rms" in f.data:
            snap.dterm_rms[f.data.get("axis_name", "?")] = f.data["rms"]
        elif f.category == Category.FILTER and "reduction_pct" in f.data:
            snap.filter_reduction[f.data.get("axis_name", "?")] = f.data["reduction_pct"]

    # Prescription
    if prescription:
        snap.n_changes = len(prescription.changes)
        snap.changes_summary = [
            f"{c.setting}: {c.old_value}→{c.new_value}"
            for c in prescription.changes
        ]
        snap.applied_changes = [
            {"setting": c.setting, "old": c.old_value, "new": c.new_value}
            for c in prescription.changes
        ]

    return snap


def build_revert_commands(snapshot: SessionSnapshot) -> str:
    """
    Generate CLI commands to revert the changes recorded in a snapshot.

    Reverts by restoring each setting's ``old`` value (only for settings
    where the new value differs), ending with ``save``.
    """
    lines = [f"# Revert session {snapshot.session_id}", ""]
    reverted = []
    for change in snapshot.applied_changes:
        setting = change.get("setting", "")
        old = change.get("old", "")
        new = change.get("new", "")
        if not setting or old == "" or old == new:
            continue
        lines.append(f"set {setting} = {old}")
        reverted.append(setting)
    if not reverted:
        lines.append("# Nothing to revert")
    else:
        lines.append("save")
    return "\n".join(lines)


# ── Comparison ────────────────────────────────────────────────────

def compare_sessions(
    older: SessionSnapshot,
    newer: SessionSnapshot,
) -> ComparisonResult:
    """
    Compare two sessions to see if tuning changes helped.

    Returns improvement/regression analysis.
    """
    result = ComparisonResult(older=older, newer=newer)

    # Compare gyro RMS
    for axis in set(list(older.gyro_rms) + list(newer.gyro_rms)):
        old_val = older.gyro_rms.get(axis)
        new_val = newer.gyro_rms.get(axis)
        if old_val is None or new_val is None:
            continue
        diff = new_val - old_val
        if abs(diff) < 1.0:
            result.unchanged.append(f"Gyro {axis}: {old_val:.1f} → {new_val:.1f} (stable)")
        elif diff < 0:
            pct = abs(diff / old_val * 100) if old_val > 0 else 0
            result.improvements.append(
                f"Gyro {axis}: {old_val:.1f} → {new_val:.1f} "
                f"({pct:.0f}% reduction) ✅"
            )
        else:
            pct = abs(diff / old_val * 100) if old_val > 0 else 0
            result.regressions.append(
                f"Gyro {axis}: {old_val:.1f} → {new_val:.1f} "
                f"({pct:.0f}% increase) ⚠️"
            )

    # Compare D-term RMS
    for axis in set(list(older.dterm_rms) + list(newer.dterm_rms)):
        old_val = older.dterm_rms.get(axis)
        new_val = newer.dterm_rms.get(axis)
        if old_val is None or new_val is None:
            continue
        diff = new_val - old_val
        if abs(diff) < 2.0:
            result.unchanged.append(f"D-term {axis}: {old_val:.1f} → {new_val:.1f}")
        elif diff < 0:
            result.improvements.append(
                f"D-term {axis}: {old_val:.1f} → {new_val:.1f} ✅"
            )
        else:
            result.regressions.append(
                f"D-term {axis}: {old_val:.1f} → {new_val:.1f} ⚠️"
            )

    # Compare findings counts
    old_bad = older.n_critical + older.n_warning
    new_bad = newer.n_critical + newer.n_warning
    if new_bad < old_bad:
        result.improvements.append(
            f"Total issues: {old_bad} → {new_bad} (fewer problems) ✅"
        )
    elif new_bad > old_bad:
        result.regressions.append(
            f"Total issues: {old_bad} → {new_bad} (more problems) ⚠️"
        )

    return result
