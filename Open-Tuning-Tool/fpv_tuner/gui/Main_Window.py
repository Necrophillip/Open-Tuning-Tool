import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QTabWidget, QWidget,
    QDockWidget, QListWidget, QVBoxLayout, QPushButton, QListWidgetItem,
    QToolBar, QStyle, QStackedWidget
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from fpv_tuner.gui.worker import LogLoaderWorker
from fpv_tuner.gui.noise_tab import NoiseTab
from fpv_tuner.gui.trace_tab import TraceTab
from fpv_tuner.gui.step_response_tab import StepResponseTab
from fpv_tuner.ui.wizard_shell import WizardShell
from fpv_tuner.ui.app_state import AppState
from fpv_tuner.ui.theme import Colors, Spacing, Typography

class MainWindow(QMainWindow):
    start_loading = pyqtSignal(list, bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FPV Blackbox Tuner")
        self.setGeometry(100, 100, 1400, 900)
        self.setMinimumSize(900, 600)
        self.loaded_logs = {}

        # Central app state shared between wizard and advanced views
        self.app_state = AppState(self)

        self._create_central_stack()
        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_file_manager_dock()
        self._init_worker_thread()

        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.showMessage("Ready — drop a log to get started")

    def _create_central_stack(self):
        """Central widget switches between Wizard and Advanced (tabs) modes."""
        self.central_stack = QStackedWidget()

        # Mode 0: Wizard
        self.wizard = WizardShell(self.app_state)
        self.wizard.advanced_mode_requested.connect(self._show_advanced)
        self.central_stack.addWidget(self.wizard)

        # Mode 1: Advanced tabs
        self.tabs = QTabWidget()
        self.trace_tab = TraceTab()
        self.noise_tab = NoiseTab()
        self.step_response_tab = StepResponseTab()
        self.tabs.addTab(self.trace_tab, "Trace Viewer")
        self.tabs.addTab(self.noise_tab, "Noise Analysis")
        self.tabs.addTab(self.step_response_tab, "Step Response")
        self.central_stack.addWidget(self.tabs)

        self.setCentralWidget(self.central_stack)

        # Start in wizard mode
        self.central_stack.setCurrentIndex(0)

    def _show_advanced(self):
        """Switch from wizard to advanced tab view."""
        self.central_stack.setCurrentIndex(1)
        self.dock.setVisible(True)

    def _show_wizard(self):
        """Switch back to wizard mode."""
        self.central_stack.setCurrentIndex(0)
        self.dock.setVisible(False)

    def _init_worker_thread(self):
        self._worker_thread = QThread()
        self.worker = LogLoaderWorker()
        self.worker.moveToThread(self._worker_thread)
        self.start_loading.connect(self.worker.process_files)
        self.worker.finished.connect(self.on_load_finished)
        self.worker.progress.connect(self.on_load_progress)
        self.worker.all_finished.connect(self.on_all_loads_finished)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.start()

    def closeEvent(self, event):
        if self._worker_thread.isRunning():
            self._worker_thread.quit()
            if not self._worker_thread.wait(1000):
                print("Warning: Log loader thread did not terminate gracefully.")
        event.accept()

    def _create_actions(self):
        style = self.style()
        icon = style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton) if style else QAction().icon()
        self.open_action = QAction(icon, "&Open Blackbox Log(s)...", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.setStatusTip("Open one or more log files")
        self.open_action.triggered.connect(self.open_log_files)

        clear_icon = style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon) if style else QAction().icon()
        self.clear_action = QAction(clear_icon, "&Clear All Logs", self)
        self.clear_action.setStatusTip("Remove all loaded logs")
        self.clear_action.triggered.connect(self.clear_all_logs)

        # View mode toggle
        self.view_wizard_action = QAction("🧙 &Wizard Mode", self)
        self.view_wizard_action.setShortcut("Ctrl+1")
        self.view_wizard_action.setStatusTip("Switch to guided wizard view")
        self.view_wizard_action.triggered.connect(self._show_wizard)

        self.view_advanced_action = QAction("🔬 &Advanced Mode", self)
        self.view_advanced_action.setShortcut("Ctrl+2")
        self.view_advanced_action.setStatusTip("Switch to advanced analysis tabs")
        self.view_advanced_action.triggered.connect(self._show_advanced)

        # Toggle for merging all segments vs picking the longest one
        self.merge_segments_action = QAction("&Merge All Segments", self)
        self.merge_segments_action.setCheckable(True)
        self.merge_segments_action.setChecked(True)
        self.merge_segments_action.setStatusTip(
            "When a BBL file contains multiple sessions, merge them all into "
            "a single continuous log (checked) or use only the longest segment (unchecked)"
        )

        self.exit_action = QAction("&Exit", self)
        self.exit_action.setStatusTip("Exit the application")
        self.exit_action.triggered.connect(self.close)

    def _create_menus(self):
        menu_bar = self.menuBar()
        if menu_bar is None:
            return
        file_menu = menu_bar.addMenu("&File")
        if file_menu:
            file_menu.addAction(self.open_action)
            file_menu.addAction(self.clear_action)
            file_menu.addSeparator()
            file_menu.addAction(self.merge_segments_action)
            file_menu.addSeparator()
            file_menu.addAction(self.exit_action)

        view_menu = menu_bar.addMenu("&View")
        if view_menu:
            view_menu.addAction(self.view_wizard_action)
            view_menu.addAction(self.view_advanced_action)

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
        # Start hidden (wizard mode is default)
        self.dock.setVisible(False)

    def open_log_files(self):
        if not self.open_action.isEnabled():
            return

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
        self.clear_action.setEnabled(False)
        merge = self.merge_segments_action.isChecked()
        self.start_loading.emit(new_files, merge)

    def on_load_progress(self, message):
        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.showMessage(message)

    def on_load_finished(self, file_path, df, pids, error):
        if error:
            QMessageBox.critical(self, "Error Loading File", f"Failed to load {os.path.basename(file_path)}:\n\n{error}")
        else:
            self.loaded_logs[file_path] = {'df': df, 'pids': pids}
            item = QListWidgetItem(os.path.basename(file_path))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            self.log_list_widget.addItem(item)
        self.update_all_tabs()

    def on_all_loads_finished(self):
        self.open_action.setEnabled(True)
        self.clear_action.setEnabled(True)
        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.showMessage("Ready", 3000)

    def remove_selected_logs(self):
        for i in reversed(range(self.log_list_widget.count())):
            item = self.log_list_widget.item(i)
            if item and item.isSelected():
                file_path = item.data(Qt.ItemDataRole.UserRole)
                if file_path in self.loaded_logs:
                    del self.loaded_logs[file_path]
                self.log_list_widget.takeItem(i)
        self.update_all_tabs()

    def clear_all_logs(self):
        self.loaded_logs.clear()
        self.log_list_widget.clear()
        self.update_all_tabs()

    def on_log_selection_changed(self, item):
        self.update_all_tabs()

    def update_all_tabs(self):
        selected_logs = {}
        for i in range(self.log_list_widget.count()):
            item = self.log_list_widget.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                file_path = item.data(Qt.ItemDataRole.UserRole)
                if file_path in self.loaded_logs:
                    selected_logs[file_path] = self.loaded_logs[file_path]
        self.trace_tab.set_data(selected_logs)
        self.noise_tab.set_data(selected_logs)
        self.step_response_tab.set_data(selected_logs)
