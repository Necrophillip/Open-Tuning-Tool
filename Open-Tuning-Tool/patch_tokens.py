import re
with open("fpv_tuner/ui/theme/tokens.py", "r") as f:
    code = f.read()

# Update Colors
code = code.replace('BG_APP = "#0B0E14"', 'BG_APP = "#0F172A"')
code = code.replace('BG_SURFACE = "#131720"', 'BG_SURFACE = "#192134"')
code = code.replace('BG_ELEVATED = "#1A1F2B"', 'BG_ELEVATED = "#1E293B"')
code = code.replace('BG_OVERLAY = "#222939"', 'BG_OVERLAY = "#334155"')

code = code.replace('ACCENT = "#4CC2FF"', 'ACCENT = "#6366F1"')
code = code.replace('ACCENT_HOVER = "#6FCFFF"', 'ACCENT_HOVER = "#818CF8"')
code = code.replace('ACCENT_PRESSED = "#33A8E8"', 'ACCENT_PRESSED = "#4F46E5"')
code = code.replace('ACCENT_MUTED = "#1E3A4D"', 'ACCENT_MUTED = "#312E81"')

# Update Typography
code = code.replace('SIZE_DISPLAY = 28', 'SIZE_DISPLAY = 32')
code = code.replace('SIZE_TITLE = 20', 'SIZE_TITLE = 24')
code = code.replace('SIZE_HEADING = 16', 'SIZE_HEADING = 18')
code = code.replace('SIZE_BODY = 13', 'SIZE_BODY = 14')
code = code.replace('SIZE_CAPTION = 11', 'SIZE_CAPTION = 12')

with open("fpv_tuner/ui/theme/tokens.py", "w") as f:
    f.write(code)
