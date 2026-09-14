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
from fpv_tuner.ui.widgets.bbl_select_dialog import BblSelectDialog
from fpv_tuner.ui.extraction_flow import ExtractionFlow
from fpv_tuner.ui.app_state import AppState, LogSession, make_cli_dump
from fpv_tuner.ui.theme import Colors, Spacing, Typography
from fpv_tuner.ui.toasts import ToastManager


class LogPage(WizardPage):
    STEP_TITLE = "Load Log"
    STEP_SUBTITLE = "Drop a blackbox log file"

    def __init__(self, state: AppState, job_runner, parent=None):
        self._jobs = job_runner
        self._current_job = None
        self._extract_flow = None
        super().__init__(state, parent)
        self.toasts = ToastManager(self)

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
        extract_row.addWidget(self.extract_btn)

        self.sync_btn = QPushButton("🔗  Sync Settings from FC")
        self.sync_btn.setProperty("variant", "ghost")
        self.sync_btn.setToolTip(
            "Read the current CLI dump from a connected flight controller."
        )
        self.sync_btn.clicked.connect(self._on_sync_clicked)
        extract_row.addWidget(self.sync_btn)

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
            df, pids, headers, error = load_log(file_path, merge_all_segments=True)
            if error:
                raise RuntimeError(error)
            job.report_progress(90, "Parsing headers...")
            return df, pids, headers

        self._current_job = self._jobs.run(
            fn=_load,
            on_result=lambda result: self._on_load_success(file_path, result),
            on_error=self._on_load_error,
            on_finished=lambda: self.progress.hide(),
        )

    def _on_load_success(self, file_path, result):
        df, pids, headers = result
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
            headers=headers or {},
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

    # ── Extract from FC (mass-storage mode + auto CLI dump) ───────

    def _on_extract_clicked(self):
        port = SerialPortDialog.get_port(self, "Extract Blackbox from FC")
        if not port:
            return

        self.extract_btn.setEnabled(False)
        self.sync_btn.setEnabled(False)
        self.progress.show()
        self.info_card.hide()

        flow = ExtractionFlow(self._jobs, self)
        flow.progress.connect(lambda msg: self._set_extract_status(f"⏳  {msg}"))
        flow.files_found.connect(self._on_bbl_files_found)
        flow.reconnect_required.connect(self._on_reconnect_required)
        flow.finished.connect(self._on_extract_finished)
        flow.failed.connect(self._on_extract_error)
        self._extract_flow = flow

        from fpv_tuner.core.serial.msc import default_extraction_dir
        flow.start(port, default_extraction_dir())
    def _on_bbl_files_found(self, files):
        chosen = BblSelectDialog.choose(files, self)
        if chosen:
            self._extract_flow.select(chosen)
        else:
            self._extract_flow = None
            self._reset_extract_buttons()

    def _on_reconnect_required(self):
        self.toasts.warning(
            "Unplug and reconnect the FC USB cable to continue.", 8000
        )

    def _on_extract_finished(self, bbl_path, cli_data):
        # Store the auto-extracted CLI dump.
        if cli_data is not None:
            self.state.set_cli(make_cli_dump(cli_data))
            self.toasts.success(
                f"CLI dump loaded — BF {cli_data.version or '?'} "
                f"({len(cli_data.settings)} settings)"
            )
        self._reset_extract_buttons()
        # Load the extracted blackbox log through the normal pipeline.
        self._on_files_dropped([bbl_path])

    def _on_extract_error(self, error_msg: str):
        self._reset_extract_buttons()
        self.info_card.setText(
            f"❌  Extraction failed: {error_msg}"
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

    def _set_extract_status(self, text: str):
        self.info_card.setText(text)
        self.info_card.setStyleSheet(f"""
            background-color: {Colors.ACCENT_MUTED};
            color: {Colors.ACCENT};
            border: 1px solid {Colors.ACCENT};
            border-radius: 10px;
            padding: {Spacing.MD}px;
            font-size: {Typography.SIZE_BODY}px;
        """)
        self.info_card.show()

    def _reset_extract_buttons(self):
        self.extract_btn.setEnabled(True)
        self.sync_btn.setEnabled(True)
        self.progress.hide()

    # ── Sync CLI dump from FC ─────────────────────────────────────

    def _on_sync_clicked(self):
        port = SerialPortDialog.get_port(self, "Sync Settings from FC")
        if not port:
            return

        self.sync_btn.setEnabled(False)
        self.toasts.info("Reading CLI dump from the flight controller...")

        def _run(job):
            from fpv_tuner.core.serial.cli import read_dump
            job.report_progress(30, "Connecting to FC...")
            return read_dump(port)

        self._jobs.run(
            fn=_run,
            on_result=self._on_sync_done,
            on_error=lambda e: self._on_sync_error(e, None),
        )

    def _on_sync_done(self, cli_data):
        self.sync_btn.setEnabled(True)
        if cli_data.errors:
            self.toasts.error("; ".join(cli_data.errors))
            return
        self.state.set_cli(make_cli_dump(cli_data))
        self.toasts.success(
            f"CLI dump loaded — BF {cli_data.version or '?'} "
            f"({len(cli_data.settings)} settings)"
        )

    def _on_sync_error(self, error_msg, _):
        self.sync_btn.setEnabled(True)
        self.toasts.error(error_msg.splitlines()[-1] if error_msg else "Sync failed")

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
