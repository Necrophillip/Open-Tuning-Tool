with open("fpv_tuner/core/pid_tuning/gyro_filter_analyzer.py", "r") as f:
    code = f.read()

target = 'f"RPM filter active — disable gyro LPF1 ({current}→0 Hz) to remove "\\\n            f"unnecessary filter delay."'

if target in code:
    print("Found exact target!")
else:
    # Just do a regex or replace the hardcoded string
    import re
    code = re.sub(r'f"RPM filter active — disable gyro LPF1 \(\{current\}→0 Hz\) to remove "\\\s*f"unnecessary filter delay\."', 
                  r'f"RPM filter active — disable gyro LPF1 ({current}→0 Hz) to remove unnecessary filter delay.\\n\\n⏱️ Latencia Estimada Ahorrada: ~0.8 ms"', code)
    with open("fpv_tuner/core/pid_tuning/gyro_filter_analyzer.py", "w") as f:
        f.write(code)
