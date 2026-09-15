import numpy as np
import pandas as pd
from fpv_tuner.analysis.step_response import analyze_step_response

def test_compound_step_truncation():
    pid_loop_hz = 400
    duration_s = 2.0
    t = np.linspace(0, duration_s, int(pid_loop_hz * duration_s))
    time_us = t * 1e6
    
    # Create RC command
    u = np.zeros_like(t)
    
    # Step 1 at t=0.5s (main step)
    step1_idx = int(0.5 * pid_loop_hz)
    u[step1_idx:] = 500.0
    
    # Step 2 at t=0.8s (secondary step within the 0.5s post-window)
    # The post window would normally extend to t=1.0s
    step2_idx = int(0.8 * pid_loop_hz)
    u[step2_idx:] = 600.0 # Jump of 100 (smaller than 500)
    
    # Create synthetic output signal
    y = np.zeros_like(t)
    y[step1_idx:] = 450.0 * (1 - np.exp(-(t[step1_idx:] - 0.5) / 0.05))
    y[step2_idx:] += 100.0 * (1 - np.exp(-(t[step2_idx:] - 0.8) / 0.05))
    
    # We expect the window to truncate before step2_idx
    result = analyze_step_response(time_us, u, y, pid_loop_hz=pid_loop_hz, plot=False, step_threshold=100)
    
    # Extract the segmented time
    t_seg = result['t_segment']
    
    # The normal post window is 0.5s (200 samples). So without truncation, length would be ~208 samples.
    # The step happens at 0.5s. Step 2 happens at 0.8s. 
    # That is 0.3s after step 1. 0.3s * 400Hz = 120 samples.
    # So the segmented window length should be strictly less than 200.
    
    original_window_expected = int(0.02 * pid_loop_hz) + int(0.5 * pid_loop_hz) + 1
    
    print(f"Original full window would be: {original_window_expected} samples")
    print(f"Actual truncated window is: {len(t_seg)} samples")
    print(f"Truncated window duration: {t_seg[-1] - t_seg[0]:.3f} s")
    
    assert len(t_seg) < original_window_expected, "Window was not truncated!"
    assert (t_seg[-1] - t_seg[0]) < 0.4, "Window duration is too long, should have truncated before 0.3s mark!"
    
    print("Test passed! Compound step successfully truncated.")

if __name__ == "__main__":
    test_compound_step_truncation()
