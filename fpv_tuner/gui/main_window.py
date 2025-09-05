import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QTabWidget, QWidget,
    QDockWidget, QListWidget, QVBoxLayout, QPushButton, QListWidgetItem,
    QToolBar, QStyle
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QThread
from fpv_tuner.gui.worker import LogLoaderWorker
from fpv_tuner.gui.noise_tab import NoiseTab
from fpv_tuner.gui.trace_tab import TraceTab
from fpv_tuner.gui.step_response_tab import StepResponseTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FPV Blackbox Tuner")
        self.setGeometry(100, 100, 1400, 900)

        self.loaded_logs = {}
        self.thread = None
        self.worker = None

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.trace_tab = TraceTab()
        self.noise_tab = NoiseTab()
        self.step_response_tab = StepResponseTab()

        self.tabs.addTab(self.trace_tab, "Trace Viewer")
        self.tabs.addTab(self.noise_tab, "Noise Analysis")
        self.tabs.addTab(self.step_response_tab, "Step Response")

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_file_manager_dock()
        self.statusBar().showMessage("Ready")

    def closeEvent(self, event):
        """
        Ensure the worker thread is stopped correctly before closing the window.
        """
        if self.thread is not None and self.thread.isRunning():
            self.thread.quit()
            # Wait a reasonable amount of time for the thread to finish
            if not self.thread.wait(1000): # 1 second timeout
                print("Warning: Log loader thread did not terminate gracefully.")
        event.accept()

    def _create_actions(self):
        # Central place for all actions
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        self.open_action = QAction(icon, "&Open Blackbox Log(s)...", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.setStatusTip("Open one or more log files")
        self.open_action.triggered.connect(self.open_log_files)

        clear_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
        self.clear_action = QAction(clear_icon, "&Clear All Logs", self)
        self.clear_action.setStatusTip("Remove all loaded logs")
        self.clear_action.triggered.connect(self.clear_all_logs)

        self.exit_action = QAction("&Exit", self)
        self.exit_action.setStatusTip("Exit the application")
        self.exit_action.triggered.connect(self.close)

    def _create_menus(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.open_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

    def _create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.clear_action)

    def _create_file_manager_dock(self):
        self.dock = QDockWidget("Loaded Logs", self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock)
        dock_widget = QWidget()
        dock_layout = QVBoxLayout(dock_widget)
        self.log_list_widget = QListWidget()
        self.log_list_widget.itemChanged.connect(self.on_log_selection_changed)
        dock_layout.addWidget(self.log_list_widget)
        remove_button = QPushButton("Remove Selected")
        remove_button.clicked.connect(self.remove_selected_logs)
        dock_layout.addWidget(remove_button)
        self.dock.setWidget(dock_widget)

    def open_log_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Open Blackbox Log Files", "", "Blackbox Logs (*.bbl *.bfl *.csv);;All Files (*)"
        )
        if not file_paths:
            return

        new_files = [fp for fp in file_paths if fp not in self.loaded_logs]
        if not new_files:
            QMessageBox.information(self, "Info", "All selected files are already loaded.")
            return

        self.open_action.setEnabled(False)
        self.thread = QThread()
        self.worker = LogLoaderWorker(new_files)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_load_finished)
        self.worker.progress.connect(self.on_load_progress)
        self.worker.all_finished.connect(self.on_all_loads_finished) # Connect new signal
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_load_progress(self, message):
        self.statusBar().showMessage(message)

    def on_load_finished(self, file_path, df, error):
        if error:
            QMessageBox.critical(self, "Error Loading File", f"Failed to load {os.path.basename(file_path)}:\n\n{error}")
        else:
            self.loaded_logs[file_path] = df
            item = QListWidgetItem(os.path.basename(file_path))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            self.log_list_widget.addItem(item)

        # This logic needs to be improved to check if all files from the worker are done
        # For now, we update tabs after each file and re-enable at the end.
        self.update_all_tabs()

    def on_all_loads_finished(self):
        """
        Called when the worker has finished processing all files.
        """
        self.open_action.setEnabled(True)
        self.statusBar().showMessage("Ready", 3000)
        # It's good practice to nullify the thread/worker after they are done
        self.thread = None
        self.worker = None

    def remove_selected_logs(self):
        for i in reversed(range(self.log_list_widget.count())):
            item = self.log_list_widget.item(i)
            if item.isSelected():
                file_path = item.data(Qt.ItemDataRole.UserRole)
                if file_path in self.loaded_logs:
                    del self.loaded_logs[file_path]
                self.log_list_widget.takeItem(i)
        self.update_all_tabs()

    def clear_all_logs(self):
        """
        Removes all loaded logs and clears the UI.
        """
        self.loaded_logs.clear()
        self.log_list_widget.clear()
        self.update_all_tabs()

    def on_log_selection_changed(self, item):
        self.update_all_tabs()

    def update_all_tabs(self):
        selected_logs = {}
        for i in range(self.log_list_widget.count()):
            item = self.log_list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                file_path = item.data(Qt.ItemDataRole.UserRole)
                if file_path in self.loaded_logs:
                    selected_logs[file_path] = self.loaded_logs[file_path]

        self.trace_tab.set_data(selected_logs)
        self.noise_tab.set_data(selected_logs)
        self.step_response_tab.set_data(selected_logs)
