import sys
from PyQt6.QtWidgets import QApplication
from fpv_tuner.gui.main_window import MainWindow

def main():
    """Main function to run the application."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
