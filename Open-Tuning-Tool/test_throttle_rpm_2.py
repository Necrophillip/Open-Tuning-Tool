import pandas as pd
df = pd.read_csv('/tmp/btfl_001_1514833200000000000_34.01.csv')
df.columns = [c.strip() for c in df.columns]
r_cols = [c for c in df.columns if 'eRPM' in c]
rpm = df[r_cols].mean(axis=1)

motor_poles = 14
# if it's in hundreds of eRPM:
rpm_mech = (rpm * 100) / (motor_poles / 2.0)
h1_hz = rpm_mech / 60.0
print("Max H1 Hz:", h1_hz.max())
