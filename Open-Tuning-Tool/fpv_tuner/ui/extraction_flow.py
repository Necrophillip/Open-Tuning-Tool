"""
Extraction flow — orchestrates "extract BBL + auto CLI dump" end-to-end.

Coordinates the multi-step, hardware-touching sequence on the shared
JobRunner, surfacing progress and interactive decisions (file choice) to
the UI via signals.  The UI never talks to serial directly.

Flow:
    start(port, dest)
      → enter MSC + list BBL files (excludes "all")
      → 1 file: auto-select; >1: emit files_found → UI calls select(path)
      → copy chosen file + eject
      → emit reconnect_required (UI shows a toast)
      → auto-detect FC + read `dump`
      → emit finished(bbl_path, cli_data)
"""
from PyQt6.QtCore import QObject, pyqtSignal


class ExtractionFlow(QObject):
    #: progress message (str)
    progress = pyqtSignal(str)
    #: multiple files found → list of {path, name, size, date}; UI must call select()
    files_found = pyqtSignal(list)
    #: FC ejected; ask the user to reconnect the USB cable
    reconnect_required = pyqtSignal()
    #: finished(bbl_path: str, cli_data: CliDumpData)
    finished = pyqtSignal(str, object)
    #: failed(message: str)
    failed = pyqtSignal(str)

    def __init__(self, jobs, parent=None):
        super().__init__(parent)
        self._jobs = jobs
        self._port = None
        self._dest = None
        self._mount = None
        self._bbl_path = None

    # ── Public API ────────────────────────────────────────────────

    def start(self, port: str, dest_dir: str):
        self._port = port
        self._dest = dest_dir
        self.progress.emit("Entering mass-storage mode...")
        self._jobs.run(
            fn=self._stage_list,
            on_result=self._on_listed,
            on_error=self._on_error,
        )

    def select(self, path: str):
        """Continue with the chosen blackbox file (auto or user-selected)."""
        self._bbl_path = path
        self.progress.emit("Copying blackbox file...")
        self._jobs.run(
            fn=lambda job: self._stage_copy(job, path),
            on_result=self._on_copied,
            on_error=self._on_error,
        )

    # ── Stages (run on background threads) ────────────────────────

    def _stage_list(self, job):
        from fpv_tuner.core.serial.msc import enter_and_list_blackbox
        job.report_progress(30, "Entering mass-storage mode...")
        mount, files = enter_and_list_blackbox(self._port)
        self._mount = mount
        return files

    def _stage_copy(self, job, path):
        from fpv_tuner.core.serial.msc import copy_blackbox_file, eject
        job.report_progress(60, "Copying blackbox file...")
        copied = copy_blackbox_file(path, self._dest)
        self._bbl_path = copied
        eject(self._mount)
        return copied

    def _stage_dump(self, job):
        from fpv_tuner.core.serial.autodetect import detect_flight_controller
        from fpv_tuner.core.serial.cli import read_dump

        job.report_progress(75, "Waiting for the flight controller...")
        port = detect_flight_controller(timeout=60.0)
        if not port:
            raise RuntimeError(
                "Flight controller not detected. Reconnect the USB cable and try again."
            )
        job.report_progress(90, "Reading CLI dump...")
        return read_dump(port)

    # ── Result handlers (main thread) ─────────────────────────────

    def _on_listed(self, files):
        if not files:
            self.failed.emit("No blackbox files found on the flight controller.")
            return
        if len(files) == 1:
            self.select(files[0])
            return
        from fpv_tuner.ui.widgets.bbl_select_dialog import describe_blackbox_file
        self.files_found.emit([describe_blackbox_file(f) for f in files])

    def _on_copied(self, _copied):
        self.reconnect_required.emit()
        self.progress.emit("Waiting for the flight controller to reconnect...")
        self._jobs.run(
            fn=self._stage_dump,
            on_result=self._on_dump,
            on_error=self._on_error,
        )

    def _on_dump(self, cli_data):
        self.finished.emit(self._bbl_path, cli_data)

    def _on_error(self, error_msg):
        tail = error_msg.splitlines()[-1] if error_msg else "Unknown error"
        self.failed.emit(tail)
