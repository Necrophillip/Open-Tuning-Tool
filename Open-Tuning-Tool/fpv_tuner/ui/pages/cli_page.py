"""
Step 2 — Drop your CLI dump.

The user pastes or drops a Betaflight `dump` output (.txt).
This is OPTIONAL — the wizard can proceed in "analysis only" mode.
"""
import os

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QTabWidget, QWidget,
)
from PyQt6.QtCore import Qt

from fpv_tuner.ui.pages.base_page import WizardPage
from fpv_tuner.ui.widgets.dropzone import DropZone
from fpv_tuner.ui.app_state import AppState, CliDump
from fpv_tuner.ui.theme import Colors, Spacing, Typography


class CliPage(WizardPage):
    STEP_TITLE = "CLI Dump"
    STEP_SUBTITLE = "Optional: paste or drop your Betaflight dump"

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        layout.addWidget(self._make_title("Load your CLI dump"))
        layout.addWidget(self._make_subtitle(
            "In the Betaflight Configurator, go to the CLI tab and type "
            "<b>dump</b>. Copy the full output into a text file or paste it below. "
            "This step is <b>optional</b> — you can skip it and still get "
            "noise analysis."
        ))

        # Two input modes: file drop or paste
        self.input_tabs = QTabWidget()
        self.input_tabs.setMaximumHeight(260)

        # Tab 1: Drop file
        drop_widget = QWidget()
        drop_layout = QVBoxLayout(drop_widget)
        self.dropzone = DropZone(
            title="Drop your CLI dump file",
            subtitle=".txt file with the output of 'dump'",
            icon="📄",
            valid_extensions=(".txt", ".cli", ".dump"),
        )
        self.dropzone.files_dropped.connect(self._on_file_dropped)
        drop_layout.addWidget(self.dropzone)
        self.input_tabs.addTab(drop_widget, "📂 From File")

        # Tab 2: Paste text
        paste_widget = QWidget()
        paste_layout = QVBoxLayout(paste_widget)
        self.paste_edit = QPlainTextEdit()
        self.paste_edit.setPlaceholderText(
            "Paste the full output of the `dump` command here..."
        )
        self.paste_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 10px;
                padding: {Spacing.MD}px;
                color: {Colors.TEXT_PRIMARY};
                font-family: {Typography.FAMILY_MONO};
                font-size: {Typography.SIZE_CAPTION}px;
            }}
        """)
        paste_layout.addWidget(self.paste_edit)

        paste_btn_layout = QHBoxLayout()
        paste_btn_layout.addStretch()
        self.load_paste_btn = QPushButton("Load from clipboard text")
        self.load_paste_btn.setProperty("variant", "primary")
        self.load_paste_btn.clicked.connect(self._on_paste_clicked)
        paste_btn_layout.addWidget(self.load_paste_btn)
        paste_layout.addLayout(paste_btn_layout)

        self.input_tabs.addTab(paste_widget, "📋 Paste Text")

        layout.addWidget(self.input_tabs)

        # Status card
        self.status_card = QLabel("")
        self.status_card.setWordWrap(True)
        self.status_card.hide()
        layout.addWidget(self.status_card)

        layout.addStretch()

    # ── Handlers ──────────────────────────────────────────────────

    def _on_file_dropped(self, paths: list):
        if not paths:
            return
        file_path = paths[0]
        try:
            from fpv_tuner.core.cli_dump import load_dump_file
            dump_data = load_dump_file(file_path)
            self._process_dump(dump_data, file_path)
        except Exception as e:
            self.dropzone.set_error(str(e))

    def _on_paste_clicked(self):
        text = self.paste_edit.toPlainText().strip()
        if not text:
            self._show_status("Paste the dump text first.", Colors.WARNING)
            return
        from fpv_tuner.core.cli_dump import parse_dump
        dump_data = parse_dump(text)
        self._process_dump(dump_data, "")

    def _process_dump(self, dump_data, file_path: str):
        if dump_data.errors:
            error_text = "\n".join(dump_data.errors)
            self._show_status(f"⚠️  {error_text}", Colors.WARNING)
            return

        cli = CliDump(
            raw_text=dump_data.raw_text,
            version=dump_data.version,
            settings=dump_data.settings,
            file_path=file_path,
        )
        self.state.set_cli(cli)

        n_settings = len(dump_data.settings)
        version_str = f"BF {dump_data.version}" if dump_data.version else "Unknown version"
        self._show_status(
            f"✅  Loaded {n_settings} settings — {version_str}",
            Colors.SUCCESS
        )
        if file_path:
            self.dropzone.set_success(os.path.basename(file_path),
                                      f"{n_settings} settings")
        self.validity_changed.emit()

    def _show_status(self, text: str, color: str):
        bg = Colors.SUCCESS_MUTED if color == Colors.SUCCESS else Colors.WARNING_MUTED
        self.status_card.setText(text)
        self.status_card.setStyleSheet(f"""
            background-color: {bg};
            color: {color};
            border: 1px solid {color};
            border-radius: 10px;
            padding: {Spacing.MD}px;
            font-size: {Typography.SIZE_BODY}px;
        """)
        self.status_card.show()

    # ── Contract ──────────────────────────────────────────────────

    def on_enter(self):
        if self.state.has_cli:
            version = self.state.cli.version or "?"
            self._show_status(
                f"✅  CLI dump loaded — BF {version}, "
                f"{len(self.state.cli.settings)} settings",
                Colors.SUCCESS
            )

    def can_proceed(self) -> bool:
        # CLI is optional — always can proceed
        return True
