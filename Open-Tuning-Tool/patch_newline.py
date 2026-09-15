with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

import re
target = 'f"mean={mean_val:.3f}\\npeak={peak_val:.3f}"'
# In the broken file, it's a literal newline, let's fix it by searching for the broken structure:
code = re.sub(r'f"mean=\{mean_val:\.3f\}\npeak=\{peak_val:\.3f\}"', r'f"mean={mean_val:.3f}\\npeak={peak_val:.3f}"', code)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
