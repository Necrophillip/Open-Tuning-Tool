with open("fpv_tuner/ui/wizard_shell.py", "r") as f:
    code = f.read()

# 1. Update WIZARD_STEPS
target_steps = """WIZARD_STEPS = [
    {"title": "Load Log",    "subtitle": "Drop a blackbox log file"},
    {"title": "Analysis",    "subtitle": "Automatic noise analysis"},
    {"title": "Diagnosis",   "subtitle": "What we found"},
    {"title": "Export",      "subtitle": "Get your new configuration"},
    {"title": "Iterate",     "subtitle": "Fly, log, repeat"},
]"""
new_steps = """WIZARD_STEPS = [
    {"title": "Load Log",    "subtitle": "Drop a blackbox log file"},
    {"title": "Analysis",    "subtitle": "Automatic noise analysis"},
    {"title": "Diagnosis",   "subtitle": "Filters & Noise"},
    {"title": "Tuning",      "subtitle": "PID & FF Engine"},
    {"title": "Export",      "subtitle": "Get your new configuration"},
    {"title": "Iterate",     "subtitle": "Fly, log, repeat"},
]"""
code = code.replace(target_steps, new_steps)

# 2. Update _go_next
target_next = """    def _go_next(self):
        if self._current_step < len(WIZARD_STEPS) - 1:
            self._go_to_step(self._current_step + 1)"""
new_next = """    def _go_next(self):
        step = self._current_step + 1
        if self.state.tuning_mode == "FILTERS" and step == 3:
            step = 4
        if self.state.tuning_mode in ("PIDS", "COMPLEMENTARY") and step == 2:
            step = 3
        if step < len(WIZARD_STEPS):
            self._go_to_step(step)"""
code = code.replace(target_next, new_next)

# 3. Update _go_back
target_back = """    def _go_back(self):
        if self._current_step > 0:
            self._go_to_step(self._current_step - 1)"""
new_back = """    def _go_back(self):
        step = self._current_step - 1
        if self.state.tuning_mode == "FILTERS" and step == 3:
            step = 2
        if self.state.tuning_mode in ("PIDS", "COMPLEMENTARY") and step == 2:
            step = 1
        if step >= 0:
            self._go_to_step(step)"""
code = code.replace(target_back, new_back)

with open("fpv_tuner/ui/wizard_shell.py", "w") as f:
    f.write(code)
