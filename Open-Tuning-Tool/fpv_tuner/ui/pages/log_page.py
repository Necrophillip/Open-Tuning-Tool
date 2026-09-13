"""
Step 1 — Drop your blackbox log.

Drag & drop a .BBL / .BFL / .CSV file. The app decodes and merges
all segments automatically in a background thread.
"""
import os

from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar
from PyQt6.QtCore import Qt

from fpv_tuner.ui.pages.base_page import WizardPage
from fpv_tuner.ui.widgets.dropzone import DropZone
from fpv_tuner.ui.widgets.serial_port_dialog import SerialPortDialog
from fpv_tuner.ui.app_state import AppState, LogSession
from fpv_tuner.ui.theme import Colors, Spacing, Typography


class LogPage(WizardPage):
    STEP_TITLE = "Load Log"
    STEP_SUBTITLE = "Drop a blackbox log file"

    def __init__(self, state: AppState, job_runner, parent=None):
        self._jobs = job_runner
        self._current_job = None
        super().__init__(state, parent)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        layout.addWidget(self._make_title("Load your Blackbox log"))
        layout.addWidget(self._make_subtitle(
            "Drag & drop your .BBL or .BFL file below. If the log contains "
            "multiple flight sessions, they will be merged automatically."
        ))

        self.dropzone = DropZone(
            title="Drop your blackbox log here",
            subtitle=".bbl, .bfl or .csv  —  or click to browse",
            icon="🚁",
            valid_extensions=(".bbl", ".bfl", ".csv"),
        )
        self.dropzone.files_dropped.connect(self._on_files_dropped)
        layout.addWidget(self.dropzone, 1)

        # Extract directly from a connected flight controller
        extract_row = QHBoxLayout()
        self.extract_btn = QPushButton("🛰  Extract from Flight Controller")
        self.extract_btn.setProperty("variant", "ghost")
        self.extract_btn.setToolTip(
            "Connect the FC via USB and pull its blackbox log via mass-storage mode."
        )
        self.extract_btn.clicked.connect(self._on_extract_clicked)
        extract_row.addStretch()
        extract_row.addWidget(self.extract_btn)
        extract_row.addStretch()
        layout.addLayout(extract_row)

        # Progress bar (hidden by default)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate
        self.progress.hide()
        layout.addWidget(self.progress)

        # Info card shown after successful load
        self.info_card = QLabel("")
        self.info_card.setWordWrap(True)
        self.info_card.setStyleSheet(f"""
            background-color: {Colors.SUCCESS_MUTED};
            color: {Colors.SUCCESS};
            border: 1px solid {Colors.SUCCESS};
            border-radius: 10px;
            padding: {Spacing.MD}px;
            font-size: {Typography.SIZE_BODY}px;
        """)
        self.info_card.hide()
        layout.addWidget(self.info_card)

        layout.addStretch()

    # ── Drop handler ──────────────────────────────────────────────

    def _on_files_dropped(self, paths: list):
        if not paths:
            return
        file_path = paths[0]  # Take the first file

        self.dropzone.set_enabled(False)
        self.progress.show()
        self.info_card.hide()

        def _load(job):
            from fpv_tuner.blackbox.loader import load_log
            job.report_progress(10, "Decoding...")
            df, pids, error = load_log(file_path, merge_all_segments=True)
            if error:
                raise RuntimeError(error)
            job.report_progress(90, "Parsing headers...")
            return df, pids

        self._current_job = self._jobs.run(
            fn=_load,
            on_result=lambda result: self._on_load_success(file_path, result),
            on_error=self._on_load_error,
            on_finished=lambda: self.progress.hide(),
        )

    def _on_load_success(self, file_path, result):
        df, pids = result
        n_rows = len(df)

        # Estimate duration
        duration_s = 0.0
        time_col = next(
            (c for c in df.columns if "time" in c.lower() and "us" in c.lower()),
            None
        )
        if time_col and n_rows > 1:
            duration_s = (df[time_col].iloc[-1] - df[time_col].iloc[0]) / 1e6

        session = LogSession(
            file_path=file_path,
            dataframe=df,
            pids=pids or {},
            n_rows=n_rows,
            duration_s=duration_s,
        )
        self.state.set_log(session)

        basename = os.path.basename(file_path)
        mins = int(duration_s // 60)
        secs = int(duration_s % 60)
        self.dropzone.set_success(basename, f"{n_rows:,} samples")
        self.info_card.setText(
            f"✅  {basename}  —  {n_rows:,} samples, "
            f"{mins}m {secs}s of flight data"
        )
        self.info_card.show()
        self.dropzone.set_enabled(True)
        self.validity_changed.emit()

    def _on_load_error(self, error_msg: str):
        self.dropzone.set_error(error_msg.splitlines()[-1] if error_msg else "Unknown error")
        self.dropzone.set_enabled(True)
        self.validity_changed.emit()

    # ── Extract from FC (mass-storage mode) ───────────────────────

    def _on_extract_clicked(self):
        port = SerialPortDialog.get_port(self, "Extract Blackbox from FC")
        if not port:
            return

        self.extract_btn.setEnabled(False)
        self.progress.show()
        self.info_card.hide()

        dest_dir = os.path.expanduser("~/Downloads")

        def _run(job):
            from fpv_tuner.core.serial.msc import extract_bbl
            from fpv_tuner.blackbox.loader import load_log

            job.report_progress(20, "Entering mass-storage mode...")
            result = extract_bbl(port, dest_dir)
            job.report_progress(80, "Loading extracted log...")
            df, pids, error = load_log(result["bbl_files"][0], merge_all_segments=True)
            if error:
                raise RuntimeError(error)
            return result["bbl_files"][0], df, pids

        self._jobs.run(
            fn=_run,
            on_result=self._on_extract_success,
            on_error=self._on_extract_error,
            on_finished=self._on_extract_finished,
        )

    def _on_extract_success(self, result):
        file_path, df, pids = result
        self._on_load_success(file_path, (df, pids))

    def _on_extract_error(self, error_msg: str):
        self.info_card.setText(
            f"❌  Extraction failed: {error_msg.splitlines()[-1] if error_msg else 'Unknown error'}"
        )
        self.info_card.setStyleSheet(f"""
            background-color: {Colors.DANGER_MUTED};
            color: {Colors.DANGER};
            border: 1px solid {Colors.DANGER};
            border-radius: 10px;
            padding: {Spacing.MD}px;
            font-size: {Typography.SIZE_BODY}px;
        """)
        self.info_card.show()

    def _on_extract_finished(self):
        self.extract_btn.setEnabled(True)
        self.progress.hide()

    # ── Contract ──────────────────────────────────────────────────

    def on_enter(self):
        if self.state.has_log:
            basename = os.path.basename(self.state.log.file_path)
            self.dropzone.set_success(basename)
            self.info_card.setText(
                f"✅  {basename}  —  {self.state.log.n_rows:,} samples"
            )
            self.info_card.show()

    def can_proceed(self) -> bool:
        return self.state.has_log
