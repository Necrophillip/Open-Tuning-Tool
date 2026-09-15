with open("fpv_tuner/analysis/summary.py", "r") as f:
    code = f.read()

import re

target = r'''        # Interpolate against throttle
        # We need raw throttle without clipping to map properly, but 'throttle' series is already 0-100
        valid_idx = throttle\.notna\(\) & harmonics_df\['h1_hz'\]\.notna\(\)
        t_clean = throttle\[valid_idx\]\.values
        
        if len\(t_clean\) > 0:
            sort_idx = np\.argsort\(t_clean\)
            t_sorted = t_clean\[sort_idx\]
            
            for h_col, key in \[\('h1_hz', 'h1'\), \('h2_hz', 'h2'\), \('h3_hz', 'h3'\)\]:
                h_vals = harmonics_df\[h_col\]\[valid_idx\]\.values
                h_sorted = h_vals\[sort_idx\]
                binned_h = np\.interp\(tc, t_sorted, h_sorted\)
                result\[key\] = binned_h'''

replacement = """        # Group harmonics into the exact same throttle bins
        import pandas as pd
        valid_idx = throttle.notna() & harmonics_df['h1_hz'].notna()
        t_clean = throttle[valid_idx].values
        
        if len(t_clean) > 0:
            bins = np.linspace(0.0, 100.0, len(tc) + 1)
            bin_indices = np.digitize(t_clean, bins) - 1
            bin_indices = np.clip(bin_indices, 0, len(tc) - 1)
            
            df_h = pd.DataFrame({'bin': bin_indices})
            for h_col, key in [('h1_hz', 'h1'), ('h2_hz', 'h2'), ('h3_hz', 'h3')]:
                df_h[key] = harmonics_df[h_col][valid_idx].values
                
            mean_h = df_h.groupby('bin').mean()
            
            for key in ['h1', 'h2', 'h3']:
                binned_h = np.full(len(tc), np.nan)
                for b_idx in mean_h.index:
                    binned_h[b_idx] = mean_h.at[b_idx, key]
                
                # Interpolate missing bins
                mask = np.isnan(binned_h)
                if not mask.all():
                    binned_h[mask] = np.interp(np.flatnonzero(mask), np.flatnonzero(~mask), binned_h[~mask])
                    
                result[key] = binned_h"""

code = re.sub(target, replacement, code)

with open("fpv_tuner/analysis/summary.py", "w") as f:
    f.write(code)
