"""
Gyro filter analyser — conditional clamp.

Reducing gyro LPF1 is a *standard* practice when the RPM filter already
covers the motor-harmonic noise band (unlike D-term, where Betaflight blocks
reduction for flyaway safety).  So this analyser:

- allows reducing ``gyro_lpf1_static_hz`` (typically to 0) ONLY when the RPM
  filter is active and sufficient, tagging it ``reduces_filtering_rpm_compensated``
  (informative, non-blocking);
- otherwise applies the hard clamp (``reduces_filtering_blocked``).
"""
from __future__ import annotations

from fpv_tuner.core.pid_tuning.models import SubRecommendation
from fpv_tuner.core.pid_tuning.helpers import hget, parse_int
from fpv_tuner.core.pid_tuning.tuning_context import (
    FLAG_REDUCES_FILTERING_RPM_COMPENSATED,
    FLAG_REDUCES_FILTERING_BLOCKED,
)
from fpv_tuner.core.pid_tuning.rpm_filter import is_rpm_filter_active


def analyze(df, pids, headers, context) -> list[SubRecommendation]:
    current = parse_int(hget(headers, "gyro_lpf1_static_hz"), 0)
    if current <= 0:
        return []  # already disabled

    if not is_rpm_filter_active(headers):
        # Hard clamp: without RPM coverage, do not suggest reducing gyro filtering.
        return [SubRecommendation(
            kind="gyro_filter",
            changes={},
            reasoning=(
                f"gyro_lpf1_static_hz ({current} Hz) could be lowered, but the RPM "
                f"filter is inactive/insufficient — blocked to avoid reducing filtering."
            ),
            rule_status="verified_official",
            safety_flags=[FLAG_REDUCES_FILTERING_BLOCKED],
        )]

    # RPM filter covers the harmonic band → reducing/zeroing LPF1 is standard.
    return [SubRecommendation(
        kind="gyro_filter",
        changes={"gyro_lpf1_static_hz": 0},
        reasoning=(
            f"RPM filter active — disable gyro LPF1 ({current}→0 Hz) to remove "
            f"unnecessary filter delay."
        ),
        rule_status="verified_official",
        confidence=0.7,
        safety_flags=[FLAG_REDUCES_FILTERING_RPM_COMPENSATED],
    )]
