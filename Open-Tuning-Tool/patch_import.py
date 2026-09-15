with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

import re
code = re.sub(r'import pyqtgraph as pg', 'import pyqtgraph as pg\\nimport numpy as np', code)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
