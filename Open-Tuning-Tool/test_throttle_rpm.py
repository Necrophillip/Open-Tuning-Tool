import pandas as pd
df = pd.read_csv('/tmp/btfl_001_1514833200000000000_34.01.csv')
df.columns = [c.strip() for c in df.columns]
t_cols = [c for c in df.columns if 'rcCommand[3]' in c]
r_cols = [c for c in df.columns if 'eRPM' in c or 'escRPM' in c]
if t_cols and r_cols:
    throttle = df[t_cols[0]]
    rpm = df[r_cols].mean(axis=1)
    print("Max Throttle:", throttle.max())
    print("Max RPM raw value:", rpm.max())
    print("Median RPM at high throttle (>1500):", rpm[throttle > 1500].median())
