"""
Diagnostics Engine — rule-based flight data analysis.

Pure Python, no Qt imports.  Designed for Betaflight 4.5 defaults.

Each rule inspects the log DataFrame (+ optional CLI settings) and
produces zero or more Finding objects.  The findings are consumed by
the diagnosis page to render human-readable cards, and by the
prescription engine to generate CLI changes.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd


# ── Data structures ───────────────────────────────────────────────

class Severity(Enum):
    GOOD = "good"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Category(Enum):
    GYRO_NOISE = "gyro_noise"
    DTERM_NOISE = "dterm_noise"
    FILTER = "filter"
    FRAME_RESONANCE = "frame_resonance"
    THROTTLE_NOISE = "throttle_noise"
    PID = "pid"
    VOLTAGE = "voltage"
    GENERAL = "general"


@dataclass
class Finding:
    """One diagnostic observation with optional recommendation."""
    severity: Severity
    category: Category
    title: str
    explanation: str
    recommendation: str = ""
    # Optional numeric payload for the prescription engine
    data: dict = field(default_factory=dict)


# ── Thresholds (Betaflight 4.5 defaults as reference) ────────────

# Gyro RMS noise (°/s) thresholds
GYRO_RMS_GOOD = 15.0
GYRO_RMS_WARNING = 30.0
GYRO_RMS_CRITICAL = 50.0

# D-term RMS thresholds
DTERM_RMS_GOOD = 30.0
DTERM_RMS_WARNING = 60.0
DTERM_RMS_CRITICAL = 100.0

# Filter effectiveness: minimum % power reduction from pre→post
FILTER_REDUCTION_GOOD = 60.0    # ≥ 60 % reduction = good
FILTER_REDUCTION_WARNING = 30.0  # 30–60 % = warning

# Frame resonance: peak PSD ratio in a narrow band
RESONANCE_PEAK_RATIO = 8.0  # peak/median ratio to flag

# Throttle noise correlation
THROTTLE_CORR_WARNING = 0.4
THROTTLE_CORR_CRITICAL = 0.7

# ── Helpers ───────────────────────────────────────────────────────

def _find_time_col(df: pd.DataFrame) -> Optional[str]:
    """Find the time column (µs) in a blackbox DataFrame."""
    for c in df.columns:
        low = c.lower()
        if "time" in low and "us" in low:
            return c
    return None


def _rms(series: pd.Series) -> float:
    """Root-mean-square of a numeric series, ignoring NaN."""
    vals = series.dropna().values.astype(float)
    if len(vals) == 0:
        return 0.0
    return float(np.sqrt(np.mean(vals ** 2)))


def _throttle_pct(df: pd.DataFrame) -> Optional[pd.Series]:
    """Return throttle as 0-100 % series, or None if unavailable."""
    col = next(
        (c for c in df.columns if "rccommand" in c.lower() and "3" in c),
        None,
    ) or next(
        (c for c in df.columns if c.lower().startswith("motor[0]")),
        None,
    )
    if col is None:
        return None
    raw = df[col].astype(float)
    mn, mx = raw.min(), raw.max()
    if mx <= mn:
        return pd.Series(np.full(len(raw), 50.0), index=raw.index)
    return (raw - mn) / (mx - mn) * 100.0


def _throttle_correlation(df: pd.DataFrame, signal_col: str) -> float:
    """Pearson correlation between throttle % and a signal's rolling RMS."""
    throttle = _throttle_pct(df)
    if throttle is None or signal_col not in df.columns:
        return 0.0
    signal = df[signal_col].astype(float).abs()
    # Rolling RMS as noise envelope
    window = max(len(df) // 200, 10)
    noise_env = signal.rolling(window, center=True).apply(
        lambda x: np.sqrt(np.mean(x ** 2)), raw=True
    )
    valid = noise_env.notna() & throttle.notna()
    if valid.sum() < 20:
        return 0.0
    return float(np.corrcoef(throttle[valid], noise_env[valid])[0, 1])


def _find_resonance_peaks(
    freqs: np.ndarray, psd: np.ndarray,
    min_freq: float = 20.0,
) -> list[dict]:
    """
    Detect narrow resonant peaks in a PSD.

    Returns list of {freq_hz, amplitude, ratio} for each significant peak.
    """
    if freqs is None or psd is None or len(freqs) < 10:
        return []

    mask = freqs >= min_freq
    if mask.sum() < 5:
        return []

    f = freqs[mask]
    p = psd[mask]
    median_p = np.median(p)
    if median_p <= 0:
        return []

    # Simple peak detection: local maxima above threshold
    peaks = []
    for i in range(1, len(p) - 1):
        if p[i] > p[i - 1] and p[i] >= p[i + 1]:
            ratio = p[i] / median_p
            if ratio >= RESONANCE_PEAK_RATIO:
                peaks.append({
                    "freq_hz": float(f[i]),
                    "amplitude": float(p[i]),
                    "ratio": float(ratio),
                })
    # Sort by ratio descending, keep top 3
    peaks.sort(key=lambda x: x["ratio"], reverse=True)
    return peaks[:3]


# ── Rule implementations ─────────────────────────────────────────

def _check_gyro_noise(df: pd.DataFrame, cli: Optional[dict] = None) -> list[Finding]:
    """Check gyro noise levels on each axis."""
    findings = []
    axis_names = {0: "Roll", 1: "Pitch", 2: "Yaw"}

    for axis in range(3):
        col = f"gyroADC[{axis}]"
        if col not in df.columns:
            continue
        rms = _rms(df[col])
        name = axis_names[axis]

        if rms > GYRO_RMS_CRITICAL:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.GYRO_NOISE,
                title=f"Critical gyro noise on {name}",
                explanation=(
                    f"Gyro RMS noise on {name} is {rms:.1f} °/s — well above the "
                    f"safe threshold ({GYRO_RMS_CRITICAL:.0f} °/s). This level of "
                    f"noise is likely causing hot motors, poor flight characteristics, "
                    f"and possibly flyaways."
                ),
                recommendation=(
                    "Inspect for mechanical issues first: damaged props, loose "
                    "screws, worn motor bearings. Consider soft-mounting the FC. "
                    "Then lower gyro filter cutoffs."
                ),
                data={"axis": axis, "axis_name": name, "rms": rms},
            ))
        elif rms > GYRO_RMS_WARNING:
            findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.GYRO_NOISE,
                title=f"Elevated gyro noise on {name}",
                explanation=(
                    f"Gyro RMS noise on {name} is {rms:.1f} °/s. "
                    f"This is above ideal ({GYRO_RMS_GOOD:.0f} °/s) and could "
                    f"lead to increased motor heat and reduced propwash handling."
                ),
                recommendation=(
                    "Check prop balance and motor condition. "
                    "Consider lowering gyro lowpass filter cutoff."
                ),
                data={"axis": axis, "axis_name": name, "rms": rms},
            ))
        elif rms > GYRO_RMS_GOOD:
            findings.append(Finding(
                severity=Severity.INFO,
                category=Category.GYRO_NOISE,
                title=f"Moderate gyro noise on {name}",
                explanation=(
                    f"Gyro RMS noise on {name} is {rms:.1f} °/s — "
                    f"slightly above the ideal target of {GYRO_RMS_GOOD:.0f} °/s."
                ),
                recommendation="Minor improvement possible with prop balancing.",
                data={"axis": axis, "axis_name": name, "rms": rms},
            ))
        else:
            findings.append(Finding(
                severity=Severity.GOOD,
                category=Category.GYRO_NOISE,
                title=f"Gyro noise on {name} is clean",
                explanation=(
                    f"RMS noise of {rms:.1f} °/s on {name} — "
                    f"this is a healthy level."
                ),
                data={"axis": axis, "axis_name": name, "rms": rms},
            ))
    return findings


def _check_dterm_noise(df: pd.DataFrame, cli: Optional[dict] = None) -> list[Finding]:
    """Check D-term noise levels."""
    findings = []
    axis_names = {0: "Roll", 1: "Pitch"}

    for axis in range(2):
        col = f"axisD[{axis}]"
        if col not in df.columns:
            continue
        rms = _rms(df[col])
        name = axis_names[axis]

        if rms > DTERM_RMS_CRITICAL:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.DTERM_NOISE,
                title=f"Severe D-term noise on {name}",
                explanation=(
                    f"D-term RMS is {rms:.1f} on {name} — extremely noisy. "
                    f"This drives motors hard, causes excessive heat, and wastes "
                    f"battery."
                ),
                recommendation=(
                    "Increase D-term lowpass filtering immediately. "
                    "Check for mechanical vibration sources."
                ),
                data={"axis": axis, "axis_name": name, "rms": rms},
            ))
        elif rms > DTERM_RMS_WARNING:
            findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.DTERM_NOISE,
                title=f"Noisy D-term on {name}",
                explanation=(
                    f"D-term RMS is {rms:.1f} on {name}. Above the comfortable "
                    f"threshold of {DTERM_RMS_WARNING:.0f}."
                ),
                recommendation="Consider increasing D-term filtering slightly.",
                data={"axis": axis, "axis_name": name, "rms": rms},
            ))
        else:
            findings.append(Finding(
                severity=Severity.GOOD,
                category=Category.DTERM_NOISE,
                title=f"D-term on {name} looks clean",
                explanation=f"RMS of {rms:.1f} — within healthy range.",
                data={"axis": axis, "axis_name": name, "rms": rms},
            ))
    return findings


def _check_filter_effectiveness(df: pd.DataFrame, cli: Optional[dict] = None) -> list[Finding]:
    """Compare pre-filter (gyroUnfilt) vs post-filter (gyroADC) noise."""
    findings = []
    axis_names = {0: "Roll", 1: "Pitch", 2: "Yaw"}

    for axis in range(3):
        pre_col = f"gyroUnfilt[{axis}]"
        post_col = f"gyroADC[{axis}]"
        if pre_col not in df.columns or post_col not in df.columns:
            continue

        pre_rms = _rms(df[pre_col])
        post_rms = _rms(df[post_col])
        name = axis_names[axis]

        if pre_rms <= 0:
            continue

        reduction_pct = (1.0 - post_rms / pre_rms) * 100.0

        if reduction_pct < FILTER_REDUCTION_WARNING:
            findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.FILTER,
                title=f"Filters barely helping on {name}",
                explanation=(
                    f"Only {reduction_pct:.0f}% noise reduction from filters on {name} "
                    f"(pre: {pre_rms:.1f} → post: {post_rms:.1f}). Most noise is "
                    f"passing through."
                ),
                recommendation=(
                    "Lower the gyro lowpass filter cutoff frequency, or add "
                    "a notch filter targeting the dominant noise frequency."
                ),
                data={
                    "axis": axis, "axis_name": name,
                    "pre_rms": pre_rms, "post_rms": post_rms,
                    "reduction_pct": reduction_pct,
                },
            ))
        elif reduction_pct < FILTER_REDUCTION_GOOD:
            findings.append(Finding(
                severity=Severity.INFO,
                category=Category.FILTER,
                title=f"Moderate filter effect on {name}",
                explanation=(
                    f"{reduction_pct:.0f}% noise reduction on {name} "
                    f"(pre: {pre_rms:.1f} → post: {post_rms:.1f}). "
                    f"Decent, but could be better."
                ),
                recommendation="Consider slightly lower filter cutoffs if latency allows.",
                data={
                    "axis": axis, "axis_name": name,
                    "pre_rms": pre_rms, "post_rms": post_rms,
                    "reduction_pct": reduction_pct,
                },
            ))
        else:
            findings.append(Finding(
                severity=Severity.GOOD,
                category=Category.FILTER,
                title=f"Filters working well on {name}",
                explanation=(
                    f"{reduction_pct:.0f}% noise reduction on {name} — "
                    f"filters are doing their job."
                ),
                data={
                    "axis": axis, "axis_name": name,
                    "pre_rms": pre_rms, "post_rms": post_rms,
                    "reduction_pct": reduction_pct,
                },
            ))
    return findings


def _check_frame_resonance(df: pd.DataFrame, cli: Optional[dict] = None) -> list[Finding]:
    """Detect narrow resonant peaks in the gyro spectrum."""
    findings = []
    time_col = _find_time_col(df)
    if not time_col:
        return findings

    from fpv_tuner.analysis.noise import get_sampling_frequency, calculate_psd

    fs = get_sampling_frequency(df[time_col])
    nyquist = fs / 2.0

    for axis in range(3):
        col = f"gyroADC[{axis}]"
        if col not in df.columns:
            continue
        freqs, psd = calculate_psd(df[col], df[time_col])
        if freqs is None:
            continue
        peaks = _find_resonance_peaks(freqs, psd)
        if not peaks:
            continue

        axis_names = {0: "Roll", 1: "Pitch", 2: "Yaw"}
        name = axis_names[axis]

        for peak in peaks:
            freq = peak["freq_hz"]
            # Classify the resonance
            if freq < 80:
                source = "likely frame structural resonance"
            elif freq < 200:
                source = "likely motor/prop vibration"
            elif freq < nyquist * 0.8:
                source = "likely propeller harmonics"
            else:
                source = "high-frequency resonance"

            findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.FRAME_RESONANCE,
                title=f"Resonance at {freq:.0f} Hz on {name}",
                explanation=(
                    f"Sharp spectral peak at {freq:.0f} Hz on the {name} axis "
                    f"(amplitude {peak['ratio']:.0f}× above background). "
                    f"This is {source}."
                ),
                recommendation=(
                    f"Add a notch filter at {freq:.0f} Hz, or investigate the "
                    f"mechanical source (check for loose parts, prop damage)."
                ),
                data={
                    "axis": axis, "axis_name": name,
                    "freq_hz": freq, "ratio": peak["ratio"],
                },
            ))
    return findings


def _check_throttle_noise_correlation(df: pd.DataFrame, cli: Optional[dict] = None) -> list[Finding]:
    """Check if noise increases significantly with throttle."""
    findings = []

    for axis in range(3):
        col = f"gyroADC[{axis}]"
        if col not in df.columns:
            continue
        corr = _throttle_correlation(df, col)
        axis_names = {0: "Roll", 1: "Pitch", 2: "Yaw"}
        name = axis_names[axis]

        if abs(corr) > THROTTLE_CORR_CRITICAL:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.THROTTLE_NOISE,
                title=f"Strong throttle-noise coupling on {name}",
                explanation=(
                    f"Noise on {name} is strongly correlated with throttle "
                    f"(r = {corr:.2f}). This means the vibration source is "
                    f"directly related to motor/prop speed."
                ),
                recommendation=(
                    "Focus on prop balance, motor condition, and frame rigidity. "
                    "A dynamic notch filter would help significantly."
                ),
                data={"axis": axis, "axis_name": name, "correlation": corr},
            ))
        elif abs(corr) > THROTTLE_CORR_WARNING:
            findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.THROTTLE_NOISE,
                title=f"Moderate throttle-noise coupling on {name}",
                explanation=(
                    f"Noise on {name} increases with throttle (r = {corr:.2f})."
                ),
                recommendation="Check props and motor balance.",
                data={"axis": axis, "axis_name": name, "correlation": corr},
            ))
    return findings


def _check_voltage_sag(df: pd.DataFrame, cli: Optional[dict] = None) -> list[Finding]:
    """Check for excessive battery voltage sag."""
    findings = []

    vbat_col = next(
        (c for c in df.columns if "vbat" in c.lower() and "latest" in c.lower()),
        None,
    ) or next(
        (c for c in df.columns if "vbat" in c.lower()),
        None,
    )
    if vbat_col is None:
        return findings

    vbat = df[vbat_col].astype(float).dropna()
    if vbat.empty:
        return findings

    # vbatLatest is in 0.01V units (e.g. 1680 = 16.80V)
    vbat_volts = vbat / 100.0
    v_max = vbat_volts.max()
    v_min = vbat_volts.min()
    sag_pct = ((v_max - v_min) / v_max * 100) if v_max > 0 else 0

    if sag_pct > 25:
        findings.append(Finding(
            severity=Severity.WARNING,
            category=Category.VOLTAGE,
            title=f"Significant voltage sag ({sag_pct:.0f}%)",
            explanation=(
                f"Battery voltage dropped from {v_max:.2f}V to {v_min:.2f}V "
                f"({sag_pct:.0f}% sag). This can cause inconsistent motor "
                f"response and brownouts."
            ),
            recommendation=(
                "Check battery health (internal resistance). Consider a higher "
                "C-rating battery or reduce throttle demands."
            ),
            data={"v_max": v_max, "v_min": v_min, "sag_pct": sag_pct},
        ))
    elif sag_pct > 15:
        findings.append(Finding(
            severity=Severity.INFO,
            category=Category.VOLTAGE,
            title=f"Moderate voltage sag ({sag_pct:.0f}%)",
            explanation=(
                f"Voltage range: {v_max:.2f}V → {v_min:.2f}V. "
                f"Some sag is normal, but {sag_pct:.0f}% is noteworthy."
            ),
            recommendation="Monitor battery health.",
            data={"v_max": v_max, "v_min": v_min, "sag_pct": sag_pct},
        ))

    return findings


# ── Main entry point ─────────────────────────────────────────────

ALL_RULES = [
    _check_gyro_noise,
    _check_dterm_noise,
    _check_filter_effectiveness,
    _check_frame_resonance,
    _check_throttle_noise_correlation,
    _check_voltage_sag,
]


def run_diagnostics(
    df: pd.DataFrame,
    cli_settings: Optional[dict] = None,
) -> list[Finding]:
    """
    Run all diagnostic rules against the flight data.

    Args:
        df:           Merged blackbox DataFrame.
        cli_settings: Optional dict of CLI settings (name → value string).

    Returns:
        List of Finding objects sorted by severity (critical first).
    """
    all_findings: list[Finding] = []
    for rule in ALL_RULES:
        try:
            all_findings.extend(rule(df, cli_settings))
        except Exception as e:
            all_findings.append(Finding(
                severity=Severity.INFO,
                category=Category.GENERAL,
                title=f"Diagnostic rule error: {rule.__name__}",
                explanation=str(e),
            ))

    # Sort: critical → warning → info → good
    severity_order = {
        Severity.CRITICAL: 0,
        Severity.WARNING: 1,
        Severity.INFO: 2,
        Severity.GOOD: 3,
    }
    all_findings.sort(key=lambda f: severity_order.get(f.severity, 99))
    return all_findings
