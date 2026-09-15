import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QScrollArea, QLabel, QPushButton
from PyQt6.QtCore import QTimer

app = QApplication(sys.argv)
w = QWidget()
l = QVBoxLayout(w)

scroll = QScrollArea()
scroll.setWidgetResizable(True)
container = QWidget()
cl = QVBoxLayout(container)
cl.setContentsMargins(0,0,0,0)

for i in range(20):
    lbl = QLabel(f"Item {i}")
    lbl.setFixedHeight(50)
    lbl.setStyleSheet("background: blue; color: white; margin: 2px;")
    lbl.setVisible(False)
    cl.addWidget(lbl)

cl.addStretch()

scroll.setWidget(container)
l.addWidget(scroll)

def show_next(idx=0):
    if idx < cl.count() - 1:
        cl.itemAt(idx).widget().setVisible(True)
        QTimer.singleShot(100, lambda: show_next(idx+1))

w.show()
show_next()
# We can't actually see this because it's in a headless environment, but we can just reason about it.
