with open("fpv_tuner/analysis/harmonics.py", "r") as f:
    code = f.read()

target = "        erpm_cols = [c for c in df.columns if c.startswith('eRPM[')]"
replacement = "        erpm_cols = [c for c in df.columns if c.startswith('eRPM[') or c.startswith('escRPM[')]"

code = code.replace(target, replacement)

with open("fpv_tuner/analysis/harmonics.py", "w") as f:
    f.write(code)
