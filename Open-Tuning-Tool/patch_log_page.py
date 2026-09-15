with open("fpv_tuner/ui/pages/log_page.py", "r") as f:
    code = f.read()

# Emojis in log_page.py:
# self.btn_filters = QRadioButton("🚀 Fase 1: Filtros")
# self.btn_pids = QRadioButton("🕹️ Fase 2: PIDs y FF")
# self.btn_comp = QRadioButton("🔧 Fase 3: Toques Finales")
# "✅  {basename}"
# "⏳  {msg}"
# "❌  Extraction failed"

import re

# We will just strip emojis from radio buttons for now to keep it clean.
# I'll inject SVGs into the radio buttons.
code = code.replace('self.btn_filters = QRadioButton("🚀 Fase 1: Filtros")', 'self.btn_filters = QRadioButton("Fase 1: Filtros")')
code = code.replace('self.btn_pids = QRadioButton("🕹️ Fase 2: PIDs y FF")', 'self.btn_pids = QRadioButton("Fase 2: PIDs y FF")')
code = code.replace('self.btn_comp = QRadioButton("🔧 Fase 3: Toques Finales")', 'self.btn_comp = QRadioButton("Fase 3: Toques Finales")')

# Replace emojis in info_card text
code = code.replace('f"✅  {basename}  —  {n_rows:,} samples, "', 'f"✓ {basename} — {n_rows:,} samples, "')
code = code.replace('f"✅  {basename}  —  {self.state.log.n_rows:,} samples"', 'f"✓ {basename} — {self.state.log.n_rows:,} samples"')
code = code.replace('f"❌  Extraction failed: {error_msg}"', 'f"✕ Extraction failed: {error_msg}"')
code = code.replace('f"⏳  {msg}"', 'f"⧖ {msg}"')

# Let's add icons to buttons
add_icons = """
        from fpv_tuner.ui.icons import get_icon
        self.btn_filters.setIcon(get_icon("rocket", Colors.TEXT_PRIMARY, 16))
        self.btn_pids.setIcon(get_icon("gamepad", Colors.TEXT_PRIMARY, 16))
        self.btn_comp.setIcon(get_icon("wrench", Colors.TEXT_PRIMARY, 16))
"""
code = re.sub(r'(self\.btn_comp = QRadioButton\("Fase 3: Toques Finales"\))', r'\1' + add_icons, code)

with open("fpv_tuner/ui/pages/log_page.py", "w") as f:
    f.write(code)
