"""
D-term filter analyser — hard clamp (never reduce filtering).

Mirrors Betaflight's own Autotune flyaway-safety rule: it must never
recommend *less* D-term filtering than currently configured.  This analyser
therefore only ever *lowers* ``dterm_lpf1_static_hz`` (more filtering).
"""
from __future__ import annotations

import numpy as np

from fpv_tuner.core.pid_tuning.models import SubRecommendation
from fpv_tuner.core.pid_tuning.helpers import hget, parse_int, clamp_int
from fpv_tuner.core.pid_tuning.tuning_context import FLAG_REDUCES_FILTERING_BLOCKED
from fpv_tuner.core.pid_tuning.rule_engine import rget, rstatus


def _dterm_rms(df) -> float:
    cols = [c for c in ("axisD[0]", "axisD[1]") if c in df.columns]
    if not cols:
        return 0.0
    data = df[cols].astype(float).to_numpy()
    return float(np.sqrt(np.mean(data ** 2)))


def analyze(df, pids, headers, context, rules=None) -> list[SubRecommendation]:
    rms_high = rget(rules, "dterm_filter", "rms_high", 60.0)
    lpf_max = rget(rules, "dterm_filter", "lpf_max", 1000)
    reduction_factor = rget(rules, "dterm_filter", "reduction_factor", 0.7)
    status = rstatus(rules, "dterm_filter")

    rms = _dterm_rms(df)
    if rms < rms_high:
        return []

    current = parse_int(hget(headers, "dterm_lpf1_static_hz"), 0)
    # Lower cutoff == more filtering.  Never raise (never reduce filtering).
    target = clamp_int(int(current * reduction_factor), 0, lpf_max)

    if target >= current:
        # Already at the filtering floor — any change would reduce filtering.
        return [SubRecommendation(
            kind="dterm_filter",
            changes={},
            reasoning=(
                f"D-term RMS is {rms:.0f} °/s but dterm_lpf1_static_hz is already "
                f"at {current} Hz — no further filtering can be added safely."
            ),
            rule_status="verified_official",
            safety_flags=[FLAG_REDUCES_FILTERING_BLOCKED],
        )]

    return [SubRecommendation(
        kind="dterm_filter",
        changes={"dterm_lpf1_static_hz": target},
        reasoning=(
            f"D-term RMS is {rms:.0f} °/s — lower dterm_lpf1_static_hz "
            f"{current}→{target} Hz to add filtering."
        ),
        rule_status=status,
        confidence=0.6,
    )]
