from __future__ import annotations

from fpv_tuner.core.pid_tuning.models import SubRecommendation
from fpv_tuner.core.pid_tuning.helpers import hget, parse_int
from fpv_tuner.core.pid_tuning.rule_engine import rget, rstatus
from fpv_tuner.core.pid_tuning.helpers import clamp_int
from fpv_tuner.analysis.landing import measure_landing_bounce
import numpy as np

def analyze(df, pids, headers, context, rules=None) -> list[SubRecommendation]:
    """
    TPA EZ-Landing analyzer.
    Calculates tpa_low_rate based on measured landing bounce.
    Calculates tpa_low_breakpoint based on hover throttle.
    """
    status = rstatus(rules, "ez_landing", "heuristic_unvalidated")

    current_tpa_low_rate = parse_int(hget(headers, "tpa_low_rate"), 0)
    current_tpa_low_breakpoint = parse_int(hget(headers, "tpa_low_breakpoint"), 1050)
    
    # Check defaults to see if user customized it
    firmware_default = 0
    if context.schema:
        schema_def = context.schema.get("tpa_low_rate")
        if schema_def and schema_def.default is not None:
            firmware_default = parse_int(schema_def.default, 0)
    
    user_customized = (current_tpa_low_rate != firmware_default)

    # 1. Detect and measure landing bounce
    landing_stats = measure_landing_bounce(df)
    if not landing_stats:
        return []

    bounce_rms = landing_stats.get("bounce_rms", 0.0)

    # 2. Apply formula from tuning rules
    base_rate = rget(rules, "ez_landing", "base_rate", 10)
    bounce_multiplier = rget(rules, "ez_landing", "bounce_multiplier", 2.5)
    max_rate = rget(rules, "ez_landing", "max_rate", 60)

    calculated_rate = base_rate + (bounce_rms * bounce_multiplier)
    target_tpa_low_rate = clamp_int(int(calculated_rate), 0, max_rate)

    # 3. Dynamic Breakpoint based on hover throttle
    thr_hover = parse_int(hget(headers, "thr_hover"), 0)
    if thr_hover < 1000:
        # Try to infer from flight data
        throttle_col = next((c for c in df.columns if "rcCommand[3]" in c), None)
        if throttle_col:
            thr_vals = df[throttle_col].values
            active_thr = thr_vals[thr_vals > 1100]
            if len(active_thr) > 0:
                # 10th percentile is a good proxy for min flying throttle / hover
                thr_hover = int(np.percentile(active_thr, 10))
            else:
                thr_hover = 1350
        else:
            thr_hover = 1350

    # Ensure it's in expected 1000-2000 range
    thr_hover = clamp_int(thr_hover, 1100, 1800)
    # Set breakpoint slightly below hover
    target_tpa_low_breakpoint = thr_hover - 100

    if target_tpa_low_rate == current_tpa_low_rate and target_tpa_low_breakpoint == current_tpa_low_breakpoint:
        return []

    changes = {
        "tpa_low_rate": target_tpa_low_rate,
        "tpa_low_breakpoint": target_tpa_low_breakpoint,
        "tpa_low_always": "ON",
    }
    
    confidence = 0.5 if user_customized else 0.8
    reasoning_prefix = "Notamos que ya personalizaste este valor. Sin embargo, " if user_customized else ""
    reasoning = f"{reasoning_prefix}Detectado rebote en aterrizaje (RMS {bounce_rms:.1f}°/s). Suavizado ajustado dinámicamente con inicio en {target_tpa_low_breakpoint}us."

    return [SubRecommendation(
        kind="tpa",
        changes=changes,
        reasoning=reasoning,
        rule_status=status,
        confidence=confidence,
    )]
