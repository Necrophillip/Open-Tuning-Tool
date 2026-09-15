"""
Prescription Engine — turns findings into safe CLI changes.

Pure Python, no Qt.  Reads diagnostic Finding objects + the current
CLI settings, and produces a set of `set name = value` commands.

Every recommendation is clamped to safe tuning ranges and validated
against the versioned CLI schema (``fpv_tuner.core.cli``), so we never
suggest an invalid command or a value that could make the quad unflyable.

Targets Betaflight 4.5+ variable names (``gyro_lpf1_dyn_min_hz``,
``dyn_notch_count``, ``p_roll``, ...).  Legacy pre-4.3 names are
normalized by the schema validator.
"""
from dataclasses import dataclass, field
from typing import Optional

from fpv_tuner.core.diagnostics import Finding, Severity, Category
from fpv_tuner.core.cli import (
    get_schema,
    clamp_value,
    validate_change,
)
from fpv_tuner.core.cli.schema import CliSchema


# ── Data structures ───────────────────────────────────────────────

@dataclass
class PrescribedChange:
    """One CLI setting change with context."""
    setting: str           # e.g. "gyro_lpf1_dyn_min_hz"
    old_value: str         # current value from CLI dump
    new_value: str         # recommended value
    reason: str            # why this change is recommended
    finding_title: str     # which finding triggered it


@dataclass
class Prescription:
    """Complete set of recommended changes."""
    changes: list[PrescribedChange] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)      # general advice
    warnings: list[str] = field(default_factory=list)   # validation warnings


# ── Safe tuning ranges (policy, Betaflight 4.5+) ──────────────────
# These are narrower than the firmware's valid range on purpose: they are
# the *safe* envelope we are willing to recommend, not the hard limits.
SAFE_RANGES = {
    # Gyro filters (dynamic lowpass is the default in 4.3+)
    "gyro_lpf1_dyn_min_hz":   (80, 250),
    "gyro_lpf1_dyn_max_hz":   (250, 1000),
    "gyro_lpf1_static_hz":    (80, 500),
    "gyro_lpf2_static_hz":    (100, 500),
    "gyro_notch1_hz":         (50, 500),
    "gyro_notch1_cutoff":     (30, 450),
    "gyro_notch2_hz":         (50, 500),
    "gyro_notch2_cutoff":     (30, 450),
    # D-term filters
    "dterm_lpf1_dyn_min_hz":  (60, 250),
    "dterm_lpf1_static_hz":   (60, 250),
    "dterm_lpf2_static_hz":   (80, 300),
    "dterm_notch_hz":         (50, 500),
    "dterm_notch_cutoff":     (30, 450),
    # Dynamic notch
    "dyn_notch_count":        (1, 5),
    "dyn_notch_q":            (200, 800),
    "dyn_notch_min_hz":       (80, 200),
    "dyn_notch_max_hz":       (300, 600),
    # PIDs
    "p_roll":                 (20, 120),
    "i_roll":                 (20, 120),
    "d_roll":                 (15, 80),
    "p_pitch":                (20, 120),
    "i_pitch":                (20, 120),
    "d_pitch":                (15, 80),
    "p_yaw":                  (20, 120),
    "i_yaw":                  (20, 120),
    "d_yaw":                  (0, 50),
}

# Betaflight 4.5 defaults (fallback when the CLI dump is missing).
BF45_DEFAULTS = {
    "gyro_lpf1_dyn_min_hz":  "250",
    "gyro_lpf1_dyn_max_hz":  "500",
    "dterm_lpf1_dyn_min_hz": "250",
    "dterm_lpf1_dyn_max_hz": "500",
    "gyro_lpf1_static_hz":   "0",
    "gyro_lpf2_static_hz":   "0",
    "dterm_lpf1_static_hz":  "0",
    "dterm_lpf2_static_hz":  "0",
    "dterm_notch_hz":        "0",
    "dterm_notch_cutoff":    "0",
    "gyro_notch1_hz":        "0",
    "gyro_notch1_cutoff":    "0",
    "gyro_notch2_hz":        "0",
    "gyro_notch2_cutoff":    "0",
    "dyn_notch_count":       "3",
    "dyn_notch_q":           "500",
    "dyn_notch_min_hz":      "150",
    "dyn_notch_max_hz":      "600",
    # PIDs (fallback when no CLI dump is available; typical 5" defaults)
    "p_roll":                "45",
    "i_roll":                "45",
    "d_roll":                "30",
    "f_roll":                "100",
    "p_pitch":               "47",
    "i_pitch":               "47",
    "d_pitch":               "32",
    "f_pitch":               "100",
    "p_yaw":                 "45",
    "i_yaw":                 "45",
    "d_yaw":                 "0",
    "f_yaw":                 "100",
}


def _clamp(value: int, setting: str, schema: CliSchema) -> int:
    """Clamp a numeric value to the safe policy range, then to the schema."""
    rng = SAFE_RANGES.get(setting)
    if rng is not None:
        lo, hi = rng
        value = max(lo, min(hi, value))
    var = schema.get(setting)
    if var is not None:
        value = int(float(clamp_value(var, str(value))))
    return value


def _get_current(cli: Optional[dict], setting: str) -> str:
    """Get the current value of a setting from CLI dump or defaults."""
    if cli:
        # CLI keys may be legacy names; try exact then normalized lookups.
        for key in (setting, setting.lower()):
            if key in cli:
                return cli[key]
    return BF45_DEFAULTS.get(setting, "0")


def _int_or(text: str, fallback: int = 0) -> int:
    """Parse a CLI value as int, with fallback."""
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return fallback


# ── Prescription rules ────────────────────────────────────────────

def _prescribe_gyro_noise(
    findings: list[Finding], cli: Optional[dict], schema: CliSchema,
) -> list[PrescribedChange]:
    """Lower gyro dynamic-lowpass cutoffs when noise is high."""
    changes = []
    worst_rms = 0.0
    for f in findings:
        if f.category == Category.GYRO_NOISE and f.severity in (
            Severity.CRITICAL, Severity.WARNING,
        ):
            worst_rms = max(worst_rms, f.data.get("rms", 0))

    if worst_rms <= 0:
        return changes

    current = _int_or(_get_current(cli, "gyro_lpf1_dyn_min_hz"), 250)

    if worst_rms > 50:
        target = max(100, int(current * 0.55))
    elif worst_rms > 30:
        target = max(120, int(current * 0.75))
    else:
        return changes

    target = _clamp(target, "gyro_lpf1_dyn_min_hz", schema)
    if target < current:
        changes.append(PrescribedChange(
            setting="gyro_lpf1_dyn_min_hz",
            old_value=str(current),
            new_value=str(target),
            reason=(
                f"Gyro noise RMS is {worst_rms:.0f} °/s. Lowering the "
                f"gyro dynamic lowpass minimum from {current} to {target} Hz "
                f"will attenuate more noise."
            ),
            finding_title="Gyro noise reduction",
        ))

        # Also lower the D-term dynamic filter proportionally
        d_current = _int_or(_get_current(cli, "dterm_lpf1_dyn_min_hz"), 250)
        d_target = _clamp(max(60, int(target * 0.6)), "dterm_lpf1_dyn_min_hz", schema)
        if d_target < d_current:
            changes.append(PrescribedChange(
                setting="dterm_lpf1_dyn_min_hz",
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
    findings: list[Finding], cli: Optional[dict], schema: CliSchema,
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

        target_hz = _clamp(freq, hz_setting, schema)
        target_cutoff = _clamp(int(freq * 0.85), cutoff_setting, schema)

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
    findings: list[Finding], cli: Optional[dict], schema: CliSchema,
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
    findings: list[Finding], cli: Optional[dict], schema: CliSchema,
) -> list[PrescribedChange]:
    """Recommend filter changes when pre→post reduction is poor."""
    changes = []

    for f in findings:
        if f.category != Category.FILTER or f.severity != Severity.WARNING:
            continue
        if any(
            g.category == Category.GYRO_NOISE
            and g.severity in (Severity.CRITICAL, Severity.WARNING)
            for g in findings
        ):
            continue
        current = _int_or(_get_current(cli, "gyro_lpf1_dyn_min_hz"), 250)
        target = _clamp(max(120, int(current * 0.85)), "gyro_lpf1_dyn_min_hz", schema)
        if target < current:
            changes.append(PrescribedChange(
                setting="gyro_lpf1_dyn_min_hz",
                old_value=str(current),
                new_value=str(target),
                reason=(
                    f"Filter effectiveness on {f.data.get('axis_name', '?')} "
                    f"is low. Slightly lowering gyro dynamic lowpass minimum "
                    f"from {current} to {target} Hz."
                ),
                finding_title=f.title,
            ))
            break

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
    schema: Optional[CliSchema] = None,
    cli_version: Optional[str] = None,
) -> Prescription:
    """
    Turn diagnostic findings into safe, schema-validated CLI changes.

    Args:
        findings:     Output of run_diagnostics().
        cli_settings: Current CLI dump settings dict (or None).
        schema:       CliSchema to validate against (defaults to latest).
        cli_version:  Firmware version string (used to pick a schema when
                      ``schema`` is not provided).

    Returns:
        Prescription with all recommended changes.
    """
    if schema is None:
        schema = get_schema(cli_version)

    rx = Prescription()

    for rule in ALL_PRESCRIPTIONS:
        try:
            rx.changes.extend(rule(findings, cli_settings, schema))
        except Exception as exc:
            rx.warnings.append(f"Prescription rule {rule.__name__} failed: {exc}")

    # Deduplicate by setting (keep the most conservative value).
    seen = {}
    for change in rx.changes:
        key = change.setting
        if key not in seen:
            seen[key] = change
        else:
            old_val = _int_or(seen[key].new_value)
            new_val = _int_or(change.new_value)
            if new_val < old_val:
                seen[key] = change

    # Validate against the schema; drop invalid changes with a warning.
    validated = []
    for change in seen.values():
        try:
            problems = validate_change(schema, change.setting, change.new_value)
        except Exception as exc:
            problems = [str(exc)]
        if problems:
            rx.warnings.append(
                f"Skipped '{change.setting}' ({change.new_value}): "
                f"{'; '.join(problems)}"
            )
            continue
        validated.append(change)
    rx.changes = validated

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
