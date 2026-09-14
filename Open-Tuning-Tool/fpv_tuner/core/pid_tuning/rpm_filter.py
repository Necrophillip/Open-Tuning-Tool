"""
RPM filter status helpers.

Used by ``gyro_filter_analyzer`` (Fase 1) and ``rpm_filter_analyzer`` (Fase 3)
to decide whether the RPM filter is active and effectively covering motor
harmonic noise.
"""
from __future__ import annotations

from fpv_tuner.core.pid_tuning.helpers import hget, parse_int, parse_int_list


def is_rpm_filter_active(headers: dict) -> bool:
    """
    True when the RPM filter is enabled and has at least one active harmonic.

    RPM filtering requires bidirectional DShot, a non-zero harmonic count, and
    at least one non-zero harmonic weight.
    """
    bidir = hget(headers, "dshot_bidir").upper()
    harmonics = parse_int(hget(headers, "rpm_filter_harmonics"), 0)
    weights = parse_int_list(hget(headers, "rpm_filter_weights"))
    return bidir in ("ON", "1") and harmonics > 0 and any(w > 0 for w in weights)


def parse_rpm_weights(headers: dict) -> list[int]:
    return parse_int_list(hget(headers, "rpm_filter_weights"))
