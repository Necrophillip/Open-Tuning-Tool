import pandas as pd
import numpy as np
from fpv_tuner.analysis.summary import compute_noise_heatmap

df = pd.read_csv('/tmp/btfl_001_1514833200000000000_34.01.csv')
df.columns = [c.strip() for c in df.columns]

res = compute_noise_heatmap(df, "roll", n_throttle_bins=80, n_freq_bins=256, motor_poles=14)
tc = res['throttle']
h1 = res['h1']

print("tc length:", len(tc))
print("h1 length:", len(h1))
print("tc min/max:", np.min(tc), np.max(tc))
print("h1 min/max:", np.min(h1), np.max(h1))

for i in range(10):
    print(f"tc[{i}] = {tc[i]:.2f}, h1[{i}] = {h1[i]:.2f}")
