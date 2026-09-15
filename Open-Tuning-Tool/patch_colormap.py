with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

import re

target = r'''def _make_thermal_colormap\(\):
    positions = \[0\.0, 0\.25, 0\.5, 0\.75, 1\.0\]
    colors = \[
        \(0, 0, 0\), \(128, 0, 0\), \(255, 100, 0\), \(255, 255, 0\), \(255, 255, 255\),
    \]
    return pg\.ColorMap\(positions, colors\)'''

replacement = """def _make_thermal_colormap():
    positions = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    colors = [
        (0, 0, 0),        # Black
        (0, 0, 128),      # Dark Blue
        (0, 255, 255),    # Cyan
        (0, 255, 0),      # Green
        (255, 255, 0),    # Yellow
        (255, 0, 0)       # Red
    ]
    return pg.ColorMap(positions, colors)"""

code = re.sub(target, replacement, code)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
