"""
Step-response based PID suggestions (passive, heuristic).

This is the project's own control heuristic, NOT an official Betaflight rule.
Thresholds are tagged ``heuristic_unvalidated`` until A/B evidence exists.
"""
from __future__ import annotations

from fpv_tuner.analysis.summary import compute_step_response_summary
from fpv_tuner.core.pid_tuning.models import SubRecommendation
from fpv_tuner.core.pid_tuning.helpers import clamp_int
from fpv_tuner.core.pid_tuning.rule_engine import rget, rstatus

import math

AXES = ("roll", "pitch", "yaw")


def zeta_from_overshoot_pct(os_pct: float) -> float:
    """Inversa de OS% = exp(-pi*zeta/sqrt(1-zeta^2))*100. os_pct en (0,100)."""
    if os_pct <= 0:
        return 1.0
    if os_pct >= 100:
        return 0.0
    k = math.log(100.0 / os_pct)
    return k / math.sqrt(math.pi**2 + k**2)


def analyze(df, pids, headers, context, rules=None) -> list[SubRecommendation]:
    """Produce P/D gain suggestions per axis from step-response metrics."""
    # Umbrales recalibrados — equivalentes exactos de las bandas de overshoot originales.
    overshoot_high = rget(rules, "step_response", "overshoot_high", 20.0)
    overshoot_mid = rget(rules, "step_response", "overshoot_mid", 12.0)
    overshoot_light = 5.0 # hardcoded threshold for light overshoot

    ZETA_SEVERE = zeta_from_overshoot_pct(overshoot_high)
    ZETA_MODERATE = zeta_from_overshoot_pct(overshoot_mid)
    ZETA_LIGHT = zeta_from_overshoot_pct(overshoot_light)

    pid_max = rget(rules, "step_response", "pid_max", 250)
    status = rstatus(rules, "step_response")

    recs = []
    for axis in AXES:
        summary = compute_step_response_summary(df, axis, pids=pids)
        if summary is None:
            continue

        zeta = summary.get("zeta")
        rise_time_s = summary.get("rise_time_s")
        axis_name = axis.capitalize()

        p_cur = int(pids.get(f"p_{axis}") or 45)
        d_cur = int(pids.get(f"d_{axis}") or 30)
        p_new, d_new = p_cur, d_cur
        
        reasoning_parts = []

        # Eje 1 — balance P/D vía zeta, solo zona subamortiguada
        if zeta is not None and zeta > 0:
            if zeta < ZETA_SEVERE:
                p_new = int(p_new * 0.90)
                d_new = int(d_new * 1.10)
                reasoning_parts.append(f"ζ={zeta:.2f} (subamortiguado severo). Bajando P, subiendo D.")
            elif zeta < ZETA_MODERATE:
                p_new = int(p_new * 0.95)
                d_new = int(d_new * 1.05)
                reasoning_parts.append(f"ζ={zeta:.2f} (subamortiguado moderado). Ajuste P/D.")
            elif zeta < ZETA_LIGHT:
                p_new = int(p_new * 0.98)
                d_new = int(d_new * 1.03)
                reasoning_parts.append(f"ζ={zeta:.2f} (ligera sobreoscilación). Ajuste fino P/D.")

        # Eje 2 — responsividad vía rise_time medido (independiente de zeta)
        if rise_time_s is not None:
            if rise_time_s > 0.200:
                p_new = int(p_new * 1.10)
                reasoning_parts.append(f"Rise time {rise_time_s*1000:.0f}ms > 200ms. Subiendo P.")
            elif rise_time_s > 0.150:
                p_new = int(p_new * 1.05)
                reasoning_parts.append(f"Rise time {rise_time_s*1000:.0f}ms > 150ms. Ajuste fino de P.")

        if not reasoning_parts:
            continue

        # Clamp al +/- 20% para que la combinación de ejes no desestabilice el dron
        p_new = clamp_int(p_new, int(p_cur * 0.8), int(p_cur * 1.2))
        d_new = clamp_int(d_new, int(d_cur * 0.8), int(d_cur * 1.2))

        # Clamp a los maximos globales
        p_new = clamp_int(p_new, 0, pid_max)
        d_new = clamp_int(d_new, 0, pid_max)

        changes = {}
        if p_new != p_cur:
            changes[f"p_{axis}"] = p_new
        if d_new != d_cur:
            changes[f"d_{axis}"] = d_new

        if changes:
            reason = " ".join(reasoning_parts)
            recs.append(SubRecommendation(
                kind="pid",
                changes=changes,
                reasoning=reason,
                rule_status=status,
                confidence=0.5,
            ))
    return recs
