import sys
from PyQt6.QtWidgets import QApplication
from fpv_tuner.gui.Main_Window import MainWindow

app = QApplication(sys.argv)
try:
    window = MainWindow()
    print("GUI INSTANTIATED SUCCESSFULLY")
except Exception as e:
    print(f"GUI CRASHED: {e}")
    sys.exit(1)
