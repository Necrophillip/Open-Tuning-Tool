from __future__ import annotations
import pandas as pd
import numpy as np

from fpv_tuner.core.pid_tuning.models import SubRecommendation

def analyze_motor_clipping(df: pd.DataFrame) -> list[SubRecommendation]:
    recs = []
    
    # Motor columns are usually motor[0], motor[1], motor[2], motor[3]
    motor_cols = [c for c in df.columns if c.startswith("motor[") and "]" in c]
    if not motor_cols:
        return recs
        
    clipping_threshold = 0.99  # Motor values might be normalized 0-1, or raw
    
    # Check max value to determine normalization
    max_val = df[motor_cols[0]].max()
    is_percent = max_val <= 100
    is_raw = max_val > 1000
    
    threshold = 2000 if is_raw else (100 if is_percent else 1.0)
    clip_val = threshold * clipping_threshold
    
    total_samples = len(df)
    for col in motor_cols:
        # Number of samples where motor output is nearly maxed out
        clipping_samples = (df[col] >= clip_val).sum()
        clipping_ratio = clipping_samples / total_samples
        
        # If any single motor is clipped for more than 1.5% of the flight
        if clipping_ratio > 0.015:
            percent = clipping_ratio * 100
            recs.append(SubRecommendation(
                kind="motor_clipping",
                changes={},
                reasoning=f"El {col} está saturado al máximo durante {percent:.1f}% del log. "
                          "Esto causa pérdida intermitente de control (Washout) y excesivo calor. "
                          "Considera reducir las ganancias P o D de este eje, o revisar posibles daños físicos.",
                rule_status="heuristic_validated",
                confidence=0.85,
            ))
            break # One warning is enough for the user

    return recs
