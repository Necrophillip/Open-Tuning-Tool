import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from fpv_tuner.ui.theme import app_stylesheet, Typography
from fpv_tuner.gui.Main_Window import MainWindow

def main():
    """Main function to run the application."""
    app = QApplication(sys.argv)
    app.setApplicationName("FPV Blackbox Tuner")
    app.setOrganizationName("FPV Tuner")

    # Apply dark theme
    app.setStyleSheet(app_stylesheet())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
