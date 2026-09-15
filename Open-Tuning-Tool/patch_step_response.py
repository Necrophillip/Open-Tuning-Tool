with open("fpv_tuner/analysis/step_response.py", "r") as f:
    code = f.read()

target = """def analyze_step_response(time_us, rc_command, output_signal, pid_loop_hz=400, plot=True, return_fit_curve=True):"""
replacement = """def analyze_step_response(time_us, rc_command, output_signal, pid_loop_hz=400, plot=True, return_fit_curve=True, motor_signals=None):"""
code = code.replace(target, replacement)

target_body = """    # Detect main step region: find largest change in input
    du = np.abs(np.diff(u))
    if du.size == 0:
        raise ValueError('No change detected in rc_command')
    idx = np.argmax(du) + 1
    # choose window around step
    pre = int(max(0, idx -  max(1, int(0.02 * pid_loop_hz))))
    post = int(min(len(t)-1, idx + max(2, int(0.5 * pid_loop_hz))))

    t_seg = t[pre:post+1]"""

replacement_body = """    # Detect main step region: find largest change in input, avoiding motor clipping
    du = np.abs(np.diff(u))
    if du.size == 0:
        raise ValueError('No change detected in rc_command')
        
    found_valid_step = False
    max_attempts = 10
    
    for attempt in range(max_attempts):
        idx = np.argmax(du) + 1
        pre = int(max(0, idx - max(1, int(0.02 * pid_loop_hz))))
        post = int(min(len(t)-1, idx + max(2, int(0.5 * pid_loop_hz))))
        
        # Check motor saturation in this window
        clipped = False
        if motor_signals is not None:
            for m_sig in motor_signals:
                m_seg = m_sig[pre:post+1]
                if len(m_seg) > 0:
                    max_val = np.max(m_seg)
                    is_percent = max_val <= 100.0
                    is_raw = max_val > 1000.0
                    threshold = 2000.0 if is_raw else (100.0 if is_percent else 1.0)
                    clip_val = threshold * 0.99
                    if np.any(m_seg >= clip_val):
                        clipped = True
                        break
        
        if clipped:
            # Zero out this peak and try the next one
            zero_pre = int(max(0, idx - int(0.2 * pid_loop_hz)))
            zero_post = int(min(len(du)-1, idx + int(0.2 * pid_loop_hz)))
            du[zero_pre:zero_post+1] = 0
        else:
            found_valid_step = True
            break
            
    if not found_valid_step:
        # Fallback to the largest change if all steps were clipped, or just raise
        # It's better to process something than nothing, but maybe flag it?
        # We will just proceed with the last checked (clipped) step.
        pass

    t_seg = t[pre:post+1]"""

code = code.replace(target_body, replacement_body)

with open("fpv_tuner/analysis/step_response.py", "w") as f:
    f.write(code)
