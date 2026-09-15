import pandas as pd
from fpv_tuner.analysis.summary import compute_noise_heatmap

df = pd.read_csv('/tmp/btfl_001_1514833200000000000_34.01.csv')
# Trim spaces from column names
df.columns = [c.strip() for c in df.columns]

res = compute_noise_heatmap(df, "roll", n_throttle_bins=20, n_freq_bins=100, motor_poles=14)
print("Keys in result:", res.keys())
if 'h1' in res:
    print("H1 values:", res['h1'][:10])
else:
    print("H1 missing!")
