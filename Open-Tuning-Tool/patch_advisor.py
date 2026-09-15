with open("fpv_tuner/core/pid_tuning/advisor.py", "r") as f:
    code = f.read()

import re

# Add the import
code = code.replace("from fpv_tuner.core.pid_tuning.dyn_notch_analyzer import analyze as analyze_dyn_notch",
"""from fpv_tuner.core.pid_tuning.dyn_notch_analyzer import analyze as analyze_dyn_notch
from fpv_tuner.core.pid_tuning.motor_analyzer import analyze_motor_clipping""")

# Add to PIDS / COMPLEMENTARY stages (I'll add it to PIDS stage)
target = """        # -- PID & FF STAGE (Phase 2) --
        if mode in ("ALL", "PIDS"):
            sub_recommendations.extend(analyze_step_response(df, pids, headers, context, rules))
            sub_recommendations.extend(analyze_ff(df, headers, context, rules))"""

replacement = """        # -- PID & FF STAGE (Phase 2) --
        if mode in ("ALL", "PIDS"):
            sub_recommendations.extend(analyze_step_response(df, pids, headers, context, rules))
            sub_recommendations.extend(analyze_ff(df, headers, context, rules))
            sub_recommendations.extend(analyze_motor_clipping(df))"""

code = code.replace(target, replacement)

with open("fpv_tuner/core/pid_tuning/advisor.py", "w") as f:
    f.write(code)
