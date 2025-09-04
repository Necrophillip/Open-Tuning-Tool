from PyQt6.QtCore import QObject, pyqtSignal
from fpv_tuner.blackbox.loader import load_log

class LogLoaderWorker(QObject):
    """
    Worker thread for loading blackbox logs without freezing the GUI.
    """
    # Signal: finished(file_path, dataframe, error_string)
    finished = pyqtSignal(str, object, str)
    progress = pyqtSignal(str)

    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths

    def run(self):
        """
        Load the log files.
        """
        total_files = len(self.file_paths)
        for i, file_path in enumerate(self.file_paths):
            self.progress.emit(f"Loading file {i + 1} of {total_files}: {file_path}...")
            try:
                df, error = load_log(file_path)
                self.finished.emit(file_path, df, error)
            except Exception as e:
                self.finished.emit(file_path, None, str(e))

        self.progress.emit("Ready")
