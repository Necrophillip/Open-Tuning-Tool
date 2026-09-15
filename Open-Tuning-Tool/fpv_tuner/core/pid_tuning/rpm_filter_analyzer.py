from __future__ import annotations

import numpy as np

from fpv_tuner.core.pid_tuning.models import SubRecommendation
from fpv_tuner.core.pid_tuning.helpers import hget, parse_int, parse_int_list
from fpv_tuner.core.pid_tuning.rule_engine import rget, rstatus

def analyze(df, pids, headers, context, rules=None) -> tuple[list[SubRecommendation], dict]:
    """
    RPM filter analyzer (completo por armónico).
    Adjusts rpm_filter_weights and rpm_filter_harmonics based on noise levels.
    """
    status = rstatus(rules, "rpm_filter")
    rms_low = rget(rules, "rpm_filter", "rms_low", 15.0)
    rms_mid = rget(rules, "rpm_filter", "rms_mid", 30.0)

    bidir = hget(headers, "dshot_bidir").upper()
    if bidir not in ("ON", "1"):
        return [], {"active": False, "covered_harmonics": 0}

    harmonics = parse_int(hget(headers, "rpm_filter_harmonics"), 0)
    if harmonics == 0:
        return [], {"active": False, "covered_harmonics": 0}

    # Get gyro noise
    gyro_cols = [c for c in df.columns if c.startswith("gyroADC[")]
    if not gyro_cols:
        return [], {"active": False, "covered_harmonics": 0}

    max_rms = 0.0
    for col in gyro_cols:
        vals = df[col].dropna().values.astype(float)
        if len(vals) > 0:
            rms = float(np.sqrt(np.mean(vals ** 2)))
            max_rms = max(max_rms, rms)

    target_weights = "100,100,100"
    reasoning = ""
    covered = 3

    if max_rms < rms_low:
        target_weights = "100,0,0"
        reasoning = f"Gyro noise is very low (max {max_rms:.1f} °/s). Using 1st harmonic only to reduce delay."
        covered = 1
    elif max_rms < rms_mid:
        target_weights = "100,50,0"
        reasoning = f"Gyro noise is moderate (max {max_rms:.1f} °/s). Filtering 1st and partially 2nd harmonic."
        covered = 2
    else:
        target_weights = "100,100,100"
        reasoning = f"Gyro noise is high (max {max_rms:.1f} °/s). Keeping full RPM filtering on 3 harmonics."
        covered = 3

    current_weights = hget(headers, "rpm_filter_weights")
    rpm_state = {
        "active": True,
        "covered_harmonics": covered,
        "target_weights": target_weights
    }

    if current_weights == target_weights:
        # User requested to notify when RPM filter is already optimal,
        # but returning empty list [] means no changes are prescribed.
        # We can just return the state so dyn_notch knows.
        return [], rpm_state

    recs = [SubRecommendation(
        kind="rpm_filter",
        changes={"rpm_filter_weights": target_weights},
        reasoning=reasoning,
        rule_status=status,
        confidence=0.6,
    )]
    
    return recs, rpm_state
