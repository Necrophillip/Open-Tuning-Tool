import re

with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

target = r'''        heat_row = QHBoxLayout\(\)
        heat_row\.setSpacing\(Spacing\.SM\)
        self\._heat_plots = \{\}

        for axis in \["roll", "pitch", "yaw"\]:
            plot_item = pg\.PlotItem\(title=axis\.capitalize\(\)\)
            plot_item\.setLabel\("bottom", "Throttle \(%\)"\)
            plot_item\.setLabel\("left", "Frequency \(Hz\)"\)

            view = pg\.ImageView\(view=plot_item\)
            view\.setColorMap\(_make_thermal_colormap\(\)\)
            view\.ui\.histogram\.hide\(\)
            view\.ui\.roiBtn\.hide\(\)
            view\.ui\.menuBtn\.hide\(\)

            # CRITICAL: Override ImageView's destructive defaults AFTER construction
            view\.setMinimumHeight\(200\)

            self\._heat_plots\[axis\] = view
            heat_row\.addWidget\(view\)
        
        layout\.addLayout\(heat_row\)'''

replacement = """        self.heat_row = QHBoxLayout()
        self.heat_row.setSpacing(Spacing.SM)
        layout.addLayout(self.heat_row)
        # Graphics will be created dynamically in _render_heatmap"""

code = re.sub(target, replacement, code, flags=re.DOTALL)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
