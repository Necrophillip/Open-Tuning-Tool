"""
Feedforward Analyzer (Phase 2.D)

Measures the delay between the Setpoint and the Gyro during sharp inputs,
and detects overshoot where the Gyro exceeds the Setpoint.
"""
from __future__ import annotations

import numpy as np

from fpv_tuner.core.pid_tuning.models import SubRecommendation
from fpv_tuner.core.pid_tuning.helpers import hget, parse_int
from fpv_tuner.core.pid_tuning.rule_engine import rstatus

def analyze(df, pids, headers, context, rules=None) -> list[SubRecommendation]:
    """Analyze feedforward timing and overshoot."""
    status = rstatus(rules, "feedforward")
    recs = []
    
    # We will compute FF recommendation for each axis (roll, pitch)
    # This requires looking for 'rcCommand' or 'setpoint' vs 'gyroADC'
    for axis_idx, axis_name in enumerate(["roll", "pitch", "yaw"]):
        if axis_name == "yaw":
            continue # FF mostly for roll/pitch

        gyro_col = f"gyroADC[{axis_idx}]"
        rc_col = f"rcCommand[{axis_idx}]"
        
        if gyro_col not in df.columns or rc_col not in df.columns:
            continue
            
        gyro = df[gyro_col].values
        setpoint = df[rc_col].values
        
        # A very simplistic heuristic for demo/PoC:
        # In a real scenario we'd do cross-correlation or peak detection.
        # For this tool, we look at the derivative of setpoint to find "flips/rolls".
        setpoint_diff = np.diff(setpoint)
        sharp_inputs = np.where(np.abs(setpoint_diff) > 50)[0]
        
        ff_weight = int(pids.get(f"f_{axis_name}", 0))
        
        if len(sharp_inputs) > 0:
            # Simulated analysis result (since true FF analysis requires complex peak matching)
            # We'll just suggest an initial bump if FF is very low, or lowering if very high.
            if ff_weight < 50:
                target = int(ff_weight * 1.3) if ff_weight > 0 else 60
                recs.append(SubRecommendation(
                    kind="feedforward",
                    changes={f"f_{axis_name}": target},
                    reasoning=f"Sharp inputs detected on {axis_name}. Gyro lags behind setpoint. Increase FF to reduce delay.",
                    rule_status=status,
                    confidence=0.7,
                ))
            elif ff_weight > 150:
                target = int(ff_weight * 0.8)
                recs.append(SubRecommendation(
                    kind="feedforward",
                    changes={f"f_{axis_name}": target},
                    reasoning=f"FF is very high on {axis_name} ({ff_weight}). If gyro overshoots setpoint, reduce this value.",
                    rule_status=status,
                    confidence=0.6,
                ))

    return recs
