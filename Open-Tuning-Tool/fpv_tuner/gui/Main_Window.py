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
from fpv_tuner.ui.jobs import JobRunner
from fpv_tuner.ui.widgets.serial_port_dialog import SerialPortDialog
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

        # Background job runner for serial extraction / CLI writes
        self.jobs = JobRunner(self)

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

        self.extract_action = QAction("🛰 &Extract from Flight Controller...", self)
        self.extract_action.setStatusTip(
            "Connect the FC via USB and pull its blackbox log via mass-storage mode"
        )
        self.extract_action.triggered.connect(self.extract_from_fc)

        self.write_action = QAction("📝 &Write Changes to FC...", self)
        self.write_action.setStatusTip(
            "Connect the FC via USB and apply the recommended CLI changes"
        )
        self.write_action.triggered.connect(self.write_changes_to_fc)

        self.sync_action = QAction("🔗 &Sync Settings from FC...", self)
        self.sync_action.setStatusTip(
            "Read the current CLI dump from a connected flight controller"
        )
        self.sync_action.triggered.connect(self.sync_settings_from_fc)

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
            file_menu.addAction(self.extract_action)
            file_menu.addSeparator()
            file_menu.addAction(self.write_action)
            file_menu.addAction(self.sync_action)
            file_menu.addSeparator()
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

    def extract_from_fc(self):
        port = SerialPortDialog.get_port(self, "Extract Blackbox from FC")
        if not port:
            return

        from fpv_tuner.core.serial.msc import default_extraction_dir
        dest_dir = default_extraction_dir()
        merge = self.merge_segments_action.isChecked()
        self.extract_action.setEnabled(False)
        status_bar = self.statusBar()

        from fpv_tuner.ui.extraction_flow import ExtractionFlow
        from fpv_tuner.ui.widgets.bbl_select_dialog import BblSelectDialog
        from fpv_tuner.ui.app_state import CliDump
        from fpv_tuner.blackbox.loader import load_log

        self._extract_flow = ExtractionFlow(self.jobs, self)
        flow = self._extract_flow
        flow.progress.connect(lambda m: self._set_status(m))
        flow.files_found.connect(lambda files: self._choose_bbl(flow, files))
        flow.reconnect_required.connect(
            lambda: self._toast_reconnect()
        )
        flow.finished.connect(lambda bbl, cli: self._extract_finished(bbl, cli, merge))
        flow.failed.connect(self._extract_failed)
        flow.start(port, dest_dir)

    def _choose_bbl(self, flow, files):
        from fpv_tuner.ui.widgets.bbl_select_dialog import BblSelectDialog
        chosen = BblSelectDialog.choose(files, self)
        if chosen:
            flow.select(chosen)
        else:
            self.extract_action.setEnabled(True)

    def _toast_reconnect(self):
        QMessageBox.information(
            self, "Reconnect",
            "The flight controller has been ejected. "
            "Reconnect its USB cable to continue reading the CLI dump.",
        )

    def _extract_finished(self, bbl_path, cli_data, merge):
        from fpv_tuner.ui.app_state import make_cli_dump
        from fpv_tuner.blackbox.loader import load_log
        self.extract_action.setEnabled(True)
        if cli_data is not None:
            self.app_state.set_cli(make_cli_dump(cli_data))
        self._set_status("Loading extracted log...")
        df, pids, headers, error = load_log(bbl_path, merge_all_segments=merge)
        self.on_load_finished(bbl_path, df, pids, headers, error)
        self.on_all_loads_finished()

    def _extract_failed(self, message):
        self.extract_action.setEnabled(True)
        QMessageBox.critical(self, "Extraction Failed", message)
        self._set_status("Ready")

    def _set_status(self, message):
        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.showMessage(message)

    def write_changes_to_fc(self):
        analysis = self.app_state.analysis
        diff = analysis.cli_diff if analysis is not None else None
        if diff is None or not diff.has_changes:
            QMessageBox.information(
                self, "No Changes",
                "Run the wizard analysis first to generate recommended changes.",
            )
            return

        port = SerialPortDialog.get_port(self, "Write Changes to FC")
        if not port:
            return

        changes = [e for e in diff.entries if e.kind in ("changed", "added")]
        version = self.app_state.cli.version if self.app_state.has_cli else None

        self.write_action.setEnabled(False)
        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.showMessage("Writing changes to the FC...")

        def _run(job):
            from fpv_tuner.core.serial import write_changes_to_fc
            from fpv_tuner.core.cli import get_schema
            job.report_progress(30, "Connecting to FC...")
            return write_changes_to_fc(port, changes, schema=get_schema(version))

        def _done(result):
            self.write_action.setEnabled(True)
            if status_bar is not None:
                status_bar.showMessage("Ready", 3000)
            if result.success:
                QMessageBox.information(
                    self, "Success",
                    f"Applied {result.n_applied} change(s) to the flight controller.",
                )
            else:
                QMessageBox.warning(
                    self, "Write Incomplete",
                    "\n".join(result.errors or ["Unknown error"]),
                )

        def _error(err):
            self.write_action.setEnabled(True)
            if status_bar is not None:
                status_bar.showMessage("Ready", 3000)
            QMessageBox.critical(self, "Write Failed", err.splitlines()[-1] if err else "Unknown error")

        self.jobs.run(fn=_run, on_result=_done, on_error=_error)

    def sync_settings_from_fc(self):
        port = SerialPortDialog.get_port(self, "Sync Settings from FC")
        if not port:
            return

        self.sync_action.setEnabled(False)
        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.showMessage("Reading CLI dump from the FC...")

        def _run(job):
            from fpv_tuner.core.serial.cli import read_dump
            job.report_progress(30, "Connecting to FC...")
            return read_dump(port)

        def _done(cli_data):
            self.sync_action.setEnabled(True)
            if status_bar is not None:
                status_bar.showMessage("Ready", 3000)
            from fpv_tuner.ui.app_state import make_cli_dump
            if cli_data.errors:
                QMessageBox.warning(self, "Sync Failed", "\n".join(cli_data.errors))
                return
            self.app_state.set_cli(make_cli_dump(cli_data))
            QMessageBox.information(
                self, "Sync Complete",
                f"Loaded CLI dump — BF {cli_data.version or '?'} "
                f"({len(cli_data.settings)} settings)",
            )

        def _error(err):
            self.sync_action.setEnabled(True)
            if status_bar is not None:
                status_bar.showMessage("Ready", 3000)
            QMessageBox.critical(self, "Sync Failed", err.splitlines()[-1] if err else "Unknown error")

        self.jobs.run(fn=_run, on_result=_done, on_error=_error)

    def on_load_finished(self, file_path, df, pids, headers, error):
        if error:
            QMessageBox.critical(self, "Error Loading File", f"Failed to load {os.path.basename(file_path)}:\n\n{error}")
        else:
            self.loaded_logs[file_path] = {'df': df, 'pids': pids, 'headers': headers}
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
