with open("fpv_tuner/analysis/harmonics.py", "r") as f:
    code = f.read()

target = """    # Calculate mechanical RPM (eRPM / magnetic pole pairs)
    rpm_mech = df[erpm_cols].mean(axis=1) / (motor_poles / 2.0)"""

replacement = """    # Calculate mechanical RPM (eRPM / magnetic pole pairs)
    # Betaflight DShot telemetry logs eRPM / 100 to save bandwidth
    true_erpm = df[erpm_cols].mean(axis=1) * 100.0
    rpm_mech = true_erpm / (motor_poles / 2.0)"""

code = code.replace(target, replacement)

with open("fpv_tuner/analysis/harmonics.py", "w") as f:
    f.write(code)
