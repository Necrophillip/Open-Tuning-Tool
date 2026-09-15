with open("fpv_tuner/analysis/summary.py", "r") as f:
    code = f.read()

code = code.replace("from fpv_tuner.analysis.noise import calculate_throttle_noise_heatmap\\nfrom fpv_tuner.analysis.harmonics import compute_motor_harmonics", 
                    "from fpv_tuner.analysis.noise import calculate_throttle_noise_heatmap\\nfrom fpv_tuner.analysis.harmonics import compute_motor_harmonics")

# actually I need to fix the explicit string issue
code = code.replace("\\nfrom fpv_tuner.analysis.harmonics import compute_motor_harmonics", 
                    "\\nfrom fpv_tuner.analysis.harmonics import compute_motor_harmonics")
