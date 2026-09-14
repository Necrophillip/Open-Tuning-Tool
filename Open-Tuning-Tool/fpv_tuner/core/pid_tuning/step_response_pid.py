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

AXES = ("roll", "pitch", "yaw")


def analyze(df, pids, headers, context, rules=None) -> list[SubRecommendation]:
    """Produce P/D gain suggestions per axis from step-response metrics."""
    overshoot_high = rget(rules, "step_response", "overshoot_high", 20.0)
    overshoot_mid = rget(rules, "step_response", "overshoot_mid", 12.0)
    rise_time_slow = rget(rules, "step_response", "rise_time_slow", 0.20)
    pid_max = rget(rules, "step_response", "pid_max", 250)
    status = rstatus(rules, "step_response")

    recs = []
    for axis in AXES:
        summary = compute_step_response_summary(df, axis, pids=pids)
        if summary is None:
            continue

        overshoot = float(summary.get("overshoot_pct", 0.0) or 0.0)
        rise_time = summary.get("rise_time_s")

        p_cur = int(pids.get(f"p_{axis}") or 45)
        d_cur = int(pids.get(f"d_{axis}") or 30)
        p_new, d_new = p_cur, d_cur

        if overshoot > overshoot_high:
            p_new = int(p_cur * 0.90)
            d_new = int(d_cur * 1.10)
            reason = f"Overshoot {overshoot:.0f}% on {axis} — reduce P and increase D."
        elif overshoot > overshoot_mid:
            p_new = int(p_cur * 0.95)
            d_new = int(d_cur * 1.05)
            reason = f"Overshoot {overshoot:.0f}% on {axis} — slightly reduce P and increase D."
        elif rise_time is not None and rise_time > rise_time_slow:
            p_new = int(p_cur * 1.10)
            reason = f"Slow rise time ({rise_time * 1000:.0f} ms) on {axis} — increase P."
        else:
            continue

        p_new = clamp_int(p_new, 0, pid_max)
        d_new = clamp_int(d_new, 0, pid_max)

        changes = {}
        if p_new != p_cur:
            changes[f"p_{axis}"] = p_new
        if d_new != d_cur:
            changes[f"d_{axis}"] = d_new

        if changes:
            recs.append(SubRecommendation(
                kind="pid",
                changes=changes,
                reasoning=reason,
                rule_status=status,
                confidence=0.5,
            ))
    return recs
