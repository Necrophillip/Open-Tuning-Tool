"""
Session History — track tuning iterations over time.

Pure Python, no Qt.  Persists each tuning session (log analysis +
diagnosis + prescription) to a local JSON store, so users can
compare iterations and see if their changes actually helped.

Storage: ~/.fpv_tuner/sessions/
Each session is a directory with metadata + findings + prescription.
"""
import json
import os
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


# ── Public API ────────────────────────────────────────────────────

def save_session(snapshot: SessionSnapshot) -> str:
    """
    Persist a session snapshot to disk.

    Returns the session ID.
    """
    if not snapshot.session_id:
        snapshot.session_id = _generate_id(snapshot.log_file, snapshot.timestamp)
    if not snapshot.timestamp:
        snapshot.timestamp = time.time()

    storage = _get_storage_dir() / snapshot.session_id
    storage.mkdir(parents=True, exist_ok=True)

    with open(storage / "snapshot.json", "w") as fh:
        json.dump(asdict(snapshot), fh, indent=2, default=str)

    return snapshot.session_id


def load_session(session_id: str) -> Optional[SessionSnapshot]:
    """Load a session by ID."""
    path = _get_storage_dir() / session_id / "snapshot.json"
    if not path.exists():
        return None
    with open(path) as fh:
        data = json.load(fh)
    return SessionSnapshot(**data)


def list_sessions(limit: int = 50) -> list[SessionSnapshot]:
    """List recent sessions, newest first."""
    storage = _get_storage_dir()
    sessions = []
    for child in storage.iterdir():
        snap_file = child / "snapshot.json"
        if not snap_file.exists():
            continue
        try:
            with open(snap_file) as fh:
                data = json.load(fh)
            sessions.append(SessionSnapshot(**data))
        except (json.JSONDecodeError, TypeError):
            continue
    sessions.sort(key=lambda s: s.timestamp, reverse=True)
    return sessions[:limit]


def delete_session(session_id: str) -> bool:
    """Delete a session directory."""
    import shutil
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
) -> SessionSnapshot:
    """
    Build a SessionSnapshot from current analysis state.

    Extracts key metrics from findings for quick comparison.
    """
    snap = SessionSnapshot(
        timestamp=time.time(),
        log_file=log_file,
        cli_version=cli_version,
        n_rows=n_rows,
        duration_s=duration_s,
        user_note=user_note,
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

    return snap


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
