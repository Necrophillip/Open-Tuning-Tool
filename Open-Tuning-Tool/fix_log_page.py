with open("fpv_tuner/ui/pages/log_page.py", "r") as f:
    lines = f.readlines()

out = []
skip = False
for line in lines:
    if "layout.addWidget(self._make_title(" in line:
        out.append(line)
        out.append("        layout.addWidget(self._make_subtitle(\"Selecciona tu misión de tuning actual y carga el log correspondiente:\"))\n")
        out.append("        from PyQt6.QtWidgets import QButtonGroup, QRadioButton\n")
        out.append("        self.mission_group = QButtonGroup(self)\n")
        out.append("        mission_layout = QHBoxLayout()\n")
        out.append("        self.btn_filters = QRadioButton(\"🚀 Fase 1: Filtros\\n(Log: Throttle Sweeps)\")\n")
        out.append("        self.btn_pids = QRadioButton(\"🕹️ Fase 2: PIDs y FF\\n(Log: Flips/Rolls Acro)\")\n")
        out.append("        self.btn_comp = QRadioButton(\"🔧 Fase 3: Toques Finales\\n(Log: Vuelo Acrobático)\")\n")
        out.append("        self.btn_filters.setChecked(True)\n")
        out.append("        self.state.tuning_mode = \"FILTERS\"\n")
        out.append("        for idx, btn in enumerate([self.btn_filters, self.btn_pids, self.btn_comp]):\n")
        out.append("            btn.setStyleSheet(f\"\"\"\n")
        out.append("                QRadioButton {{\n")
        out.append("                    font-size: 14px;\n")
        out.append("                    padding: 10px;\n")
        out.append("                    border: 1px solid {Colors.BORDER_SUBTLE};\n")
        out.append("                    border-radius: 8px;\n")
        out.append("                    background: {Colors.BG_SURFACE};\n")
        out.append("                }}\n")
        out.append("                QRadioButton:checked {{\n")
        out.append("                    border-color: {Colors.PRIMARY};\n")
        out.append("                    background: {Colors.PRIMARY_MUTED};\n")
        out.append("                }}\n")
        out.append("            \"\"\")\n")
        out.append("            self.mission_group.addButton(btn, idx)\n")
        out.append("            mission_layout.addWidget(btn)\n")
        out.append("        def _on_mission_changed(idx):\n")
        out.append("            modes = [\"FILTERS\", \"PIDS\", \"COMPLEMENTARY\"]\n")
        out.append("            self.state.tuning_mode = modes[idx]\n")
        out.append("        self.mission_group.idClicked.connect(_on_mission_changed)\n")
        out.append("        layout.addLayout(mission_layout)\n")
        skip = True
    elif "layout.addWidget(self.dropzone, 1)" in line: # I didn't replace this part, I appended before it. Wait, the dropzone setup might have been overwritten? Let's check where to resume.
        pass
        
    if skip:
        if "self.dropzone = DropZone(" in line:
            skip = False
            out.append(line)
    else:
        out.append(line)

with open("fpv_tuner/ui/pages/log_page.py", "w") as f:
    f.writelines(out)
