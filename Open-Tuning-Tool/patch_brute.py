with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    lines = f.readlines()

start = -1
end = -1
for i, line in enumerate(lines):
    if "heat_header.addWidget(self.signal_combo)" in line:
        start = i + 2
    if "btn_row = QHBoxLayout()" in line:
        end = i

new_lines = lines[:start] + [
    "        self.heat_row = QHBoxLayout()\n",
    "        self.heat_row.setSpacing(Spacing.SM)\n",
    "        layout.addLayout(self.heat_row)\n",
    "\n"
] + lines[end:]

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.writelines(new_lines)
