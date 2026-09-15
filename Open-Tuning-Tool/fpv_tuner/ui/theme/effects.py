from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor
from PyQt6.QtCore import QPoint

def apply_shadow(widget, blur=15, alpha=60, y_offset=4):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setColor(QColor(0, 0, 0, alpha))
    shadow.setOffset(0.0, float(y_offset))
    widget.setGraphicsEffect(shadow)
    return shadow
