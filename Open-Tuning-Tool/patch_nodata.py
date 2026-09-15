with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

import re
target = r'''            data = heatmaps\.get\(axis\)
            if data is None:
                continue'''

replacement = """            data = heatmaps.get(axis)
            if data is None:
                plot_item.setTitle(f"{axis.capitalize()} (No data)")
                continue"""

code = re.sub(target, replacement, code)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
