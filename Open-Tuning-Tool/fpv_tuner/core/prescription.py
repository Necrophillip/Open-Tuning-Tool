"""
Prescription Engine — turns findings into safe CLI changes.

Pure Python, no Qt.  Reads diagnostic Finding objects + the current
CLI settings, and produces a set of `set name = value` commands.

Every recommendation is clamped to safe ranges so we never suggest
something that could make the quad unflyable.
"""
from dataclasses import dataclass, field
from typing import Optional

from fpv_tuner.core.diagnostics import Finding, Severity, Category


# ── Data structures ───────────────────────────────────────────────

@dataclass
class PrescribedChange:
    """One CLI setting change with context."""
    setting: str           # e.g. "gyro_lowpass_hz"
    old_value: str         # current value from CLI dump
    new_value: str         # recommended value
    reason: str            # why this change is recommended
    finding_title: str     # which finding triggered it


@dataclass
class Prescription:
    """Complete set of recommended changes."""
    changes: list[PrescribedChange] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # general advice


# ── Safe ranges (Betaflight 4.5) ─────────────────────────────────

SAFE_RANGES = {
    # Filters
    "gyro_lowpass_hz":         (80, 500),
    "gyro_lowpass2_hz":        (100, 500),
    "gyro_lowpass_type":       None,  # enum — no numeric clamp
    "gyro_lowpass2_type":      None,
    "gyro_notch1_hz":          (50, 500),
    "gyro_notch1_cutoff":      (30, 450),
    "gyro_notch2_hz":          (50, 500),
    "gyro_notch2_cutoff":      (30, 450),
    "dterm_lowpass_hz":        (60, 250),
    "dterm_lowpass2_hz":       (80, 300),
    "dterm_lowpass_type":      None,
    "dterm_notch_hz":          (50, 500),
    "dterm_notch_cutoff":      (30, 450),
    "dyn_notch_count":         (1, 5),
    "dyn_notch_q":             (200, 800),
    "dyn_notch_min_hz":        (80, 200),
    "dyn_notch_max_hz":        (300, 600),
    # PIDs (roll axis shown, same logic for pitch/yaw)
    "p_roll":                  (20, 120),
    "i_roll":                  (20, 120),
    "d_roll":                  (15, 80),
    "p_pitch":                 (20, 120),
    "i_pitch":                 (20, 120),
    "d_pitch":                 (15, 80),
    "p_yaw":                   (20, 120),
    "i_yaw":                   (20, 120),
    "d_yaw":                   (0, 50),
}

# Betaflight 4.5 defaults (fallback when CLI dump is missing)
BF45_DEFAULTS = {
    "gyro_lowpass_hz": "250",
    "gyro_lowpass2_hz": "0",
    "dterm_lowpass_hz": "150",
    "dterm_lowpass2_hz": "0",
    "dterm_notch_hz": "0",
    "dterm_notch_cutoff": "0",
    "gyro_notch1_hz": "0",
    "gyro_notch1_cutoff": "0",
    "gyro_notch2_hz": "0",
    "gyro_notch2_cutoff": "0",
    "dyn_notch_count": "3",
    "dyn_notch_q": "500",
    "dyn_notch_min_hz": "150",
    "dyn_notch_max_hz": "600",
}


def _clamp(value: int, setting: str) -> int:
    """Clamp a numeric value to the safe range for a setting."""
    rng = SAFE_RANGES.get(setting)
    if rng is None:
        return value
    lo, hi = rng
    return max(lo, min(hi, value))


def _get_current(cli: Optional[dict], setting: str) -> str:
    """Get the current value of a setting from CLI dump or defaults."""
    if cli and setting in cli:
        return cli[setting]
    return BF45_DEFAULTS.get(setting, "0")


def _int_or(text: str, fallback: int = 0) -> int:
    """Parse a CLI value as int, with fallback."""
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return fallback


# ── Prescription rules ────────────────────────────────────────────

def _prescribe_gyro_noise(
    findings: list[Finding], cli: Optional[dict],
) -> list[PrescribedChange]:
    """Lower gyro filters when noise is high."""
    changes = []
    worst_rms = 0.0
    for f in findings:
        if f.category == Category.GYRO_NOISE and f.severity in (
            Severity.CRITICAL, Severity.WARNING,
        ):
            rms = f.data.get("rms", 0)
            worst_rms = max(worst_rms, rms)

    if worst_rms <= 0:
        return changes

    current = _int_or(_get_current(cli, "gyro_lowpass_hz"), 250)

    if worst_rms > 50:
        # Critical: aggressive reduction
        target = max(100, int(current * 0.55))
    elif worst_rms > 30:
        # Warning: moderate reduction
        target = max(120, int(current * 0.75))
    else:
        return changes

    target = _clamp(target, "gyro_lowpass_hz")
    if target < current:
        changes.append(PrescribedChange(
            setting="gyro_lowpass_hz",
            old_value=str(current),
            new_value=str(target),
            reason=(
                f"Gyro noise RMS is {worst_rms:.0f} °/s. Lowering the "
                f"gyro lowpass filter from {current} to {target} Hz "
                f"will attenuate more noise."
            ),
            finding_title="Gyro noise reduction",
        ))

        # Also lower D-term filter proportionally
        d_current = _int_or(_get_current(cli, "dterm_lowpass_hz"), 150)
        d_target = _clamp(max(60, int(target * 0.6)), "dterm_lowpass_hz")
        if d_target < d_current:
            changes.append(PrescribedChange(
                setting="dterm_lowpass_hz",
                old_value=str(d_current),
                new_value=str(d_target),
                reason=(
                    f"D-term filter should follow the gyro filter. "
                    f"Lowering from {d_current} to {d_target} Hz."
                ),
                finding_title="Gyro noise reduction",
            ))

    return changes


def _prescribe_frame_resonance(
    findings: list[Finding], cli: Optional[dict],
) -> list[PrescribedChange]:
    """Add notch filters for detected resonances."""
    changes = []
    notch_slots = 0

    for f in findings:
        if f.category != Category.FRAME_RESONANCE:
            continue
        freq = int(f.data.get("freq_hz", 0))
        if freq < 50 or freq > 500:
            continue

        if notch_slots == 0:
            hz_setting = "gyro_notch1_hz"
            cutoff_setting = "gyro_notch1_cutoff"
        elif notch_slots == 1:
            hz_setting = "gyro_notch2_hz"
            cutoff_setting = "gyro_notch2_cutoff"
        else:
            break  # Only 2 notch slots available

        target_hz = _clamp(freq, hz_setting)
        target_cutoff = _clamp(int(freq * 0.85), cutoff_setting)

        changes.append(PrescribedChange(
            setting=hz_setting,
            old_value=_get_current(cli, hz_setting),
            new_value=str(target_hz),
            reason=(
                f"Resonance detected at {freq} Hz. Adding a notch "
                f"filter to attenuate this specific frequency."
            ),
            finding_title=f.title,
        ))
        changes.append(PrescribedChange(
            setting=cutoff_setting,
            old_value=_get_current(cli, cutoff_setting),
            new_value=str(target_cutoff),
            reason=f"Notch filter cutoff for the {freq} Hz resonance.",
            finding_title=f.title,
        ))
        notch_slots += 1

    return changes


def _prescribe_throttle_coupling(
    findings: list[Finding], cli: Optional[dict],
) -> list[PrescribedChange]:
    """Enable/tune dynamic notch for throttle-correlated noise."""
    changes = []

    has_coupling = any(
        f.category == Category.THROTTLE_NOISE
        and f.severity in (Severity.CRITICAL, Severity.WARNING)
        for f in findings
    )
    if not has_coupling:
        return changes

    # Ensure dynamic notch is enabled
    dyn_count = _int_or(_get_current(cli, "dyn_notch_count"), 3)
    if dyn_count < 2:
        changes.append(PrescribedChange(
            setting="dyn_notch_count",
            old_value=str(dyn_count),
            new_value="3",
            reason=(
                "Noise correlates with throttle — dynamic notch filter "
                "tracks motor RPM and attenuates harmonics automatically."
            ),
            finding_title="Throttle-noise coupling",
        ))

    dyn_min = _int_or(_get_current(cli, "dyn_notch_min_hz"), 150)
    if dyn_min > 100:
        changes.append(PrescribedChange(
            setting="dyn_notch_min_hz",
            old_value=str(dyn_min),
            new_value="100",
            reason="Extend dynamic notch range to catch lower-frequency harmonics.",
            finding_title="Throttle-noise coupling",
        ))

    return changes


def _prescribe_filter_improvement(
    findings: list[Finding], cli: Optional[dict],
) -> list[PrescribedChange]:
    """Recommend filter changes when pre→post reduction is poor."""
    changes = []

    for f in findings:
        if f.category != Category.FILTER or f.severity != Severity.WARNING:
            continue
        # Already handled by gyro noise prescription if noise is high
        if any(
            g.category == Category.GYRO_NOISE
            and g.severity in (Severity.CRITICAL, Severity.WARNING)
            for g in findings
        ):
            continue
        # Mild improvement
        current = _int_or(_get_current(cli, "gyro_lowpass_hz"), 250)
        target = _clamp(max(120, int(current * 0.85)), "gyro_lowpass_hz")
        if target < current:
            changes.append(PrescribedChange(
                setting="gyro_lowpass_hz",
                old_value=str(current),
                new_value=str(target),
                reason=(
                    f"Filter effectiveness on {f.data.get('axis_name', '?')} "
                    f"is low. Slightly lowering gyro lowpass from {current} "
                    f"to {target} Hz."
                ),
                finding_title=f.title,
            ))
            break  # Only one adjustment

    return changes


# ── Main entry point ─────────────────────────────────────────────

ALL_PRESCRIPTIONS = [
    _prescribe_gyro_noise,
    _prescribe_frame_resonance,
    _prescribe_throttle_coupling,
    _prescribe_filter_improvement,
]


def generate_prescription(
    findings: list[Finding],
    cli_settings: Optional[dict] = None,
) -> Prescription:
    """
    Turn diagnostic findings into safe CLI changes.

    Args:
        findings:     Output of run_diagnostics().
        cli_settings: Current CLI dump settings dict (or None).

    Returns:
        Prescription with all recommended changes.
    """
    rx = Prescription()

    for rule in ALL_PRESCRIPTIONS:
        try:
            rx.changes.extend(rule(findings, cli_settings))
        except Exception:
            pass  # Don't crash on a single rule failure

    # Deduplicate by setting (keep the most conservative value)
    seen = {}
    for change in rx.changes:
        key = change.setting
        if key not in seen:
            seen[key] = change
        else:
            # Keep the lower value for filters (more filtering = safer)
            old_val = _int_or(seen[key].new_value)
            new_val = _int_or(change.new_value)
            if new_val < old_val:
                seen[key] = change
    rx.changes = list(seen.values())

    # General notes
    if any(f.severity == Severity.CRITICAL for f in findings):
        rx.notes.append(
            "⚠️ Critical issues detected. Address mechanical problems "
            "first (props, motors, mounting) before relying on filters."
        )
    if not rx.changes:
        rx.notes.append(
            "✅ No critical changes needed. Your quad looks healthy! "
            "Fly and log again to verify."
        )

    return rx
