import re

with open("fpv_tuner/ui/pages/export_page.py", "r") as f:
    code = f.read()

# Replace the layout initialization
target_layout = r'''    def _build_ui\(self\):
        layout = QVBoxLayout\(self\)
        layout\.setContentsMargins\(Spacing\.LG, Spacing\.MD, Spacing\.LG, Spacing\.MD\)
        layout\.setSpacing\(Spacing\.SM\)'''

replacement_layout = """    def _build_ui(self):
        from PyQt6.QtWidgets import QScrollArea, QFrame, QWidget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; } QWidget#scroll_content { background: transparent; }")
        
        content = QWidget()
        content.setObjectName("scroll_content")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        layout.setSpacing(Spacing.SM)
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll)"""

code = re.sub(target_layout, replacement_layout, code)

with open("fpv_tuner/ui/pages/export_page.py", "w") as f:
    f.write(code)
