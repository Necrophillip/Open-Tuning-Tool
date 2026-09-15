with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

import re

target = r'view\.setImage\(img, autoRange=False, transform=tr\)'
replacement = 'view.setImage(img, autoRange=False, autoLevels=True, transform=tr)'

code = re.sub(target, replacement, code)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
