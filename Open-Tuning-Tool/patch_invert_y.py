with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

import re
target = r'view\.ui\.menuBtn\.hide\(\)\n\s*view\.setMinimumHeight\(200\)'
replacement = 'view.ui.menuBtn.hide()\\n            view.setMinimumHeight(200)\\n            view.getView().invertY(False)'

code = re.sub(target, replacement, code)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
