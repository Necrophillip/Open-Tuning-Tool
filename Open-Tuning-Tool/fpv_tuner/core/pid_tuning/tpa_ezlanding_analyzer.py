from __future__ import annotations

from fpv_tuner.core.pid_tuning.models import SubRecommendation
from fpv_tuner.core.pid_tuning.helpers import hget, parse_int
from fpv_tuner.core.pid_tuning.rule_engine import rstatus

def analyze(df, pids, headers, context, rules=None) -> list[SubRecommendation]:
    """
    TPA EZ-Landing analyzer (dual classic/curve).
    Configures tpa_low_rate and tpa_low_breakpoint for smoother landings
    without sacrificing flight feel.
    """
    status = rstatus(rules, "tpa", "heuristic_unvalidated")

    # If tpa_low_rate already exists and is > 0, do not overwrite user preference
    tpa_low_rate = parse_int(hget(headers, "tpa_low_rate"), 0)
    if tpa_low_rate > 0:
        return []

    changes = {
        "tpa_low_rate": 50,
        "tpa_low_breakpoint": 1250,
        "tpa_low_always": "ON",
    }
    
    # "dual classic/curve": Maybe also configure regular TPA for high throttle?
    tpa_rate = parse_int(hget(headers, "tpa_rate"), 0)
    if tpa_rate == 0:
        changes["tpa_rate"] = 65
        changes["tpa_breakpoint"] = 1350
        reasoning = "Enable dual TPA: EZ-landing (low throttle) and high throttle TPA for smooth flights."
    else:
        reasoning = "Enable EZ-landing TPA (low throttle P/D reduction) to reduce bouncing on touchdown."

    return [SubRecommendation(
        kind="tpa",
        changes=changes,
        reasoning=reasoning,
        rule_status=status,
        confidence=0.8,
    )]
