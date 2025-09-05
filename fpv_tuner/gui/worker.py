from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from fpv_tuner.blackbox.loader import load_log

class LogLoaderWorker(QObject):
    """
    Worker object for loading blackbox logs without freezing the GUI.
    Designed to live in a persistent QThread.
    """
    # Signal: finished(file_path, dataframe, error_string)
    finished = pyqtSignal(str, object, str)
    progress = pyqtSignal(str)
    all_finished = pyqtSignal()

    def __init__(self):
        super().__init__()

    @pyqtSlot(list)
    def process_files(self, file_paths):
        """
        Load the log files. This is a slot connected to a signal
        from the main thread.
        """
        total_files = len(file_paths)
        for i, file_path in enumerate(file_paths):
            self.progress.emit(f"Loading file {i + 1} of {total_files}: {file_path}...")
            try:
                df, error = load_log(file_path)
                self.finished.emit(file_path, df, error)
            except Exception as e:
                self.finished.emit(file_path, None, str(e))

        self.progress.emit("Ready")
        self.all_finished.emit()
