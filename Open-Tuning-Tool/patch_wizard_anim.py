with open("fpv_tuner/ui/wizard_shell.py", "r") as f:
    code = f.read()

import re

# In _go_to_step, replace fade_in with slide_in_from_right
target = """        # Fade in the new page (skip if it has complex children like scroll areas)
        if not _has_scroll_area(self._pages[index]):
            fade_in(self._pages[index])"""
replacement = """        # Slide and fade the new page
        from fpv_tuner.ui.animations import slide_in_from_right
        if not _has_scroll_area(self._pages[index]):
            slide_in_from_right(self._pages[index], offset=20, duration=250)"""

code = code.replace(target, replacement)
with open("fpv_tuner/ui/wizard_shell.py", "w") as f:
    f.write(code)
