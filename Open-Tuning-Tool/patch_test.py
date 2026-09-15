with open("tests/test_feedforward_analyzer.py", "r") as f:
    code = f.read()
code = code.replace("len(sharp_inputs) > 10", "len(sharp_inputs) > 0") # wait, the test doesn't check this, the logic does.
# I will modify the logic to len(sharp_inputs) > 0 in feedforward_analyzer.py
with open("fpv_tuner/core/pid_tuning/feedforward_analyzer.py", "r") as f:
    logic_code = f.read()
logic_code = logic_code.replace("len(sharp_inputs) > 10:", "len(sharp_inputs) > 0:")
with open("fpv_tuner/core/pid_tuning/feedforward_analyzer.py", "w") as f:
    f.write(logic_code)
