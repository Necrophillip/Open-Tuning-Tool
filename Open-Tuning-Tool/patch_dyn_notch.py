with open("fpv_tuner/core/pid_tuning/dyn_notch_analyzer.py", "r") as f:
    code = f.read()

import re

new_code = """from __future__ import annotations

import numpy as np

from fpv_tuner.core.pid_tuning.models import SubRecommendation
from fpv_tuner.core.pid_tuning.helpers import hget, parse_int
from fpv_tuner.core.pid_tuning.rule_engine import rget, rstatus

def analyze(df, pids, headers, context, rpm_state: dict, rules=None) -> list[SubRecommendation]:
    \"\"\"
    Dynamic Notch analyzer.
    Supports both legacy dyn_notch_q (BF <4.3) and modern dyn_notch_width_percent (BF 4.3+).
    Coordinates with RPM filter coverage to avoid overlapping.
    \"\"\"
    status = rstatus(rules, "dyn_notch", "heuristic_unvalidated")

    # Detect modern firmware schema
    is_modern_notch = False
    if context.schema:
        if context.schema.get("dyn_notch_width_percent"):
            is_modern_notch = True
        elif not context.schema.get("dyn_notch_q"):
            # If neither is found in the schema, it's safer to skip or assume modern
            pass
    else:
        # Fallback to header inspection if no schema
        if hget(headers, "dyn_notch_width_percent") is not None:
            is_modern_notch = True

    # Get gyro noise
    gyro_cols = [c for c in df.columns if c.startswith("gyroADC[")]
    if not gyro_cols:
        return []

    max_rms = 0.0
    for col in gyro_cols:
        vals = df[col].dropna().values.astype(float)
        if len(vals) > 0:
            rms = float(np.sqrt(np.mean(vals ** 2)))
            max_rms = max(max_rms, rms)

    # Base heuristic thresholds
    rms_high = rget(rules, "dterm_filter", "rms_high", 60.0) 
    rms_low = 15.0

    # Current settings
    current_count = parse_int(hget(headers, "dyn_notch_count"), 3)
    current_min_hz = parse_int(hget(headers, "dyn_notch_min_hz"), 150)
    current_q = parse_int(hget(headers, "dyn_notch_q"), 500)
    current_width = parse_int(hget(headers, "dyn_notch_width_percent"), 8)
    
    changes = {}
    reasoning_parts = []
    
    rpm_covered_harmonics = rpm_state.get("covered_harmonics", 0)

    if max_rms > rms_high:
        target_count = 3
        target_min_hz = 150
        target_q = 250
        target_width = 8
        reason_noise = f"Alto nivel de ruido detectado (RMS {max_rms:.1f}°/s)."
    elif max_rms > rms_low:
        target_count = 2
        target_min_hz = 200
        target_q = 300
        target_width = 4
        reason_noise = f"Nivel de ruido moderado (RMS {max_rms:.1f}°/s)."
    else:
        target_count = 1
        target_min_hz = 250
        target_q = 500
        target_width = 0
        reason_noise = f"Ruido muy bajo (RMS {max_rms:.1f}°/s)."
        
    # Coordination with RPM filter
    if rpm_covered_harmonics >= 3 and target_count > 1:
        target_count = min(target_count, 1)
        target_min_hz = max(target_min_hz, 250) 
        reasoning_parts.append(f"{reason_noise} El filtro RPM ya cubre 3 armónicos, reduciendo Dynamic Notch a count={target_count} para evitar doble filtrado.")
    elif rpm_covered_harmonics == 0 and target_count < 3:
        target_count = 3
        target_min_hz = 150
        target_q = 250
        target_width = 8
        reasoning_parts.append(f"Filtro RPM inactivo. Maximizando Dynamic Notch (count=3).")
    else:
        reasoning_parts.append(f"{reason_noise} Ajustando Dynamic Notch a count={target_count}.")

    if target_count != current_count:
        changes["dyn_notch_count"] = target_count
    if target_min_hz != current_min_hz:
        changes["dyn_notch_min_hz"] = target_min_hz
        
    if is_modern_notch:
        if target_width != current_width:
            changes["dyn_notch_width_percent"] = target_width
            reasoning_parts.append(f"Usando schema moderno (width_percent={target_width}%).")
    else:
        if target_q != current_q:
            changes["dyn_notch_q"] = target_q
            reasoning_parts.append(f"Usando schema legacy (Q={target_q}).")
        
    if not changes:
        return []
        
    return [SubRecommendation(
        kind="filter", 
        changes=changes,
        reasoning=" ".join(reasoning_parts),
        rule_status=status,
        confidence=0.7,
    )]
"""

with open("fpv_tuner/core/pid_tuning/dyn_notch_analyzer.py", "w") as f:
    f.write(new_code)
