import sys
import os
import logging
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from fpv_tuner.ui.theme import app_stylesheet, Typography
from fpv_tuner.gui.Main_Window import MainWindow


def _setup_logging():
    """Configure console logging so serial/MSC/CLI activity is visible."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    # Focus the serial/CLI logs; keep the rest quiet.
    for name in ("fpv_tuner.core.serial", "fpv_tuner.core.cli"):
        logging.getLogger(name).setLevel(logging.DEBUG)


def main():
    """Main function to run the application."""
    _setup_logging()
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
