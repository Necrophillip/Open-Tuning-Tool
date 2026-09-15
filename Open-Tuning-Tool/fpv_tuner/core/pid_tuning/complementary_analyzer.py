"""
Complementary Analyzer (Phase 3)

Analyzes phase 3 adjustments like dynamic idle, anti-gravity, and thrust linearization.
"""
from __future__ import annotations

import numpy as np

from fpv_tuner.core.pid_tuning.models import SubRecommendation
from fpv_tuner.core.pid_tuning.helpers import hget, parse_int
from fpv_tuner.core.pid_tuning.rule_engine import rstatus

def analyze(df, pids, headers, context, rules=None) -> list[SubRecommendation]:
    recs = []
    status = rstatus(rules, "complementary")

    # 1. Dynamic Idle
    dshot_idle = parse_int(hget(headers, "dshot_idle_value"), 0)
    motor_protocol = hget(headers, "motor_pwm_protocol", "").upper()
    
    if "DSHOT" in motor_protocol and dshot_idle < 200: # 200 = 20 in some CLI scales, let's assume 0 is off or old scale.
        recs.append(SubRecommendation(
            kind="dynamic_idle",
            changes={"dshot_idle_value": 300}, # e.g. 30 in BF 4.3+ scale = 300
            reasoning="Dynamic Idle is very low or off. Setting a value between 20-40 (200-400 in CLI) drastically improves control at zero throttle and reduces propwash.",
            rule_status=status,
            confidence=0.8,
        ))

    # 2. Thrust Linearization
    thrust_linear = parse_int(hget(headers, "thrust_linear"), 0)
    if thrust_linear < 15:
        recs.append(SubRecommendation(
            kind="thrust_linearization",
            changes={"thrust_linear": 20},
            reasoning="Thrust Linearization compensates for non-linear motor thrust. A base of 15-20% is recommended for most 5-inch quads.",
            rule_status=status,
            confidence=0.7,
        ))

    # 3. Anti-Gravity
    anti_gravity = parse_int(hget(headers, "anti_gravity_gain"), 0)
    # Simple check for aggressive throttle inputs (punch outs)
    rc3 = df.get("rcCommand[3]")
    if rc3 is not None:
        rc3_diff = np.diff(rc3.astype(float))
        punch_outs = np.where(rc3_diff > 300)[0] # sharp throttle increases
        
        if len(punch_outs) > 2 and anti_gravity < 8000: # 8000 = 8.0 in old BF? It's usually 3500-8000
            recs.append(SubRecommendation(
                kind="anti_gravity",
                changes={"anti_gravity_gain": 8000},
                reasoning="Punch-outs detected. If you experience nose dips during these throttle punches, increase Anti-Gravity.",
                rule_status=status,
                confidence=0.6,
            ))

    return recs
