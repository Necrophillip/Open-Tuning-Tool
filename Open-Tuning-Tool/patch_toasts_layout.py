with open("fpv_tuner/ui/toasts.py", "r") as f:
    code = f.read()

import re

new_toast_init = """    STYLES = {
        "success": {"bg": Colors.SUCCESS_MUTED, "border": Colors.SUCCESS, "icon": "check", "color": Colors.SUCCESS},
        "error":   {"bg": Colors.DANGER_MUTED,  "border": Colors.DANGER,  "icon": "x", "color": Colors.DANGER},
        "info":    {"bg": Colors.ACCENT_MUTED,   "border": Colors.ACCENT,  "icon": "info", "color": Colors.ACCENT},
        "warning": {"bg": Colors.WARNING_MUTED,  "border": Colors.WARNING, "icon": "alert", "color": Colors.WARNING},
    }

    def __init__(self, message: str, kind: str = "info",
                 duration_ms: int = 3000, parent=None):
        super().__init__(parent)
        style = self.STYLES.get(kind, self.STYLES["info"])
        
        from fpv_tuner.ui.icons import get_pixmap
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        layout.setSpacing(Spacing.MD)
        
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_pixmap(style["icon"], style["color"], 18))
        layout.addWidget(icon_lbl)
        
        txt_lbl = QLabel(message)
        txt_lbl.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(txt_lbl)

        self.setStyleSheet(f\"\"\"
            Toast {{
                background-color: {style['bg']};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {style['border']};
                border-radius: {Radius.LG}px;
                font-size: {Typography.SIZE_BODY}px;
            }}
        \"\"\")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.adjustSize()

        from fpv_tuner.ui.theme.effects import apply_shadow
        apply_shadow(self, blur=20, alpha=60)

        self._duration = duration_ms
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)

        self._opacity_effect.setOpacity(0)
        self.hide()"""

code = re.sub(r'    STYLES = \{.*?\n        self\.hide\(\)', new_toast_init, code, flags=re.DOTALL)

with open("fpv_tuner/ui/toasts.py", "w") as f:
    f.write(code)
