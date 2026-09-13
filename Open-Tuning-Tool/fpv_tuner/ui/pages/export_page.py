"""
Step 4 — Export / Review.

Shows the analysis summary (step responses + noise heatmaps), the
recommended changes, and generates a new CLI dump ready to apply.
"""
import os

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit,
    QFileDialog, QMessageBox, QTabWidget, QWidget, QComboBox,
)
from PyQt6.QtCore import Qt

import pyqtgraph as pg

from fpv_tuner.ui.pages.base_page import WizardPage
from fpv_tuner.ui.app_state import AppState
from fpv_tuner.ui.widgets.serial_port_dialog import SerialPortDialog
from fpv_tuner.ui.theme import Colors, Spacing, Radius, Typography


def _make_thermal_colormap():
    positions = [0.0, 0.25, 0.5, 0.75, 1.0]
    colors = [
        (0, 0, 0), (128, 0, 0), (255, 100, 0), (255, 255, 0), (255, 255, 255),
    ]
    return pg.ColorMap(positions, colors)


class ExportPage(WizardPage):
    STEP_TITLE = "Export"
    STEP_SUBTITLE = "Get your new configuration"

    def __init__(self, state: AppState, job_runner=None, parent=None):
        self._jobs = job_runner
        self._diff = None
        self._schema = None
        super().__init__(state, parent)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        layout.addWidget(self._make_title("Export your configuration"))
        layout.addWidget(self._make_subtitle(
            "Based on the analysis, here are the recommended changes. "
            "Copy the CLI commands below or save the full dump."
        ))

        # ── Analysis review (step response + noise heatmaps) ──
        self.review_tabs = QTabWidget()
        self.review_tabs.setMaximumHeight(320)
        self._build_step_response_tab()
        self._build_heatmap_tab()
        layout.addWidget(self.review_tabs)

        # Changes summary
        self.changes_label = QLabel("No changes recommended yet.")
        self.changes_label.setTextFormat(Qt.TextFormat.RichText)
        self.changes_label.setWordWrap(True)
        self.changes_label.setStyleSheet(f"""
            background-color: {Colors.BG_SURFACE};
            border: 1px solid {Colors.BORDER_SUBTLE};
            border-radius: {Radius.MD}px;
            padding: {Spacing.MD}px;
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SIZE_BODY}px;
        """)
        layout.addWidget(self.changes_label)

        # CLI output preview
        self.cli_preview = QPlainTextEdit()
        self.cli_preview.setReadOnly(True)
        self.cli_preview.setPlaceholderText(
            "CLI commands will appear here after analysis..."
        )
        self.cli_preview.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {Colors.BG_APP};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Radius.MD}px;
                padding: {Spacing.MD}px;
                color: {Colors.ACCENT};
                font-family: {Typography.FAMILY_MONO};
                font-size: {Typography.SIZE_CAPTION}px;
            }}
        """)
        layout.addWidget(self.cli_preview, 1)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(Spacing.MD)

        self.copy_btn = QPushButton("📋  Copy to Clipboard")
        self.copy_btn.setProperty("variant", "primary")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        btn_layout.addWidget(self.copy_btn)

        self.save_btn = QPushButton("💾  Save to File")
        self.save_btn.setProperty("variant", "ghost")
        self.save_btn.clicked.connect(self._save_to_file)
        btn_layout.addWidget(self.save_btn)

        self.write_btn = QPushButton("🛰  Write to FC")
        self.write_btn.setProperty("variant", "primary")
        self.write_btn.setToolTip(
            "Connect the FC via USB and apply these CLI changes directly."
        )
        self.write_btn.clicked.connect(self._write_to_fc)
        btn_layout.addWidget(self.write_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Instructions
        instructions = QLabel(
            "<b>How to apply:</b><br>"
            "1. Open Betaflight Configurator<br>"
            "2. Connect your quad<br>"
            "3. Go to the CLI tab<br>"
            "4. Paste the commands and press Enter<br>"
            "5. Type <code>save</code> and press Enter<br>"
            "6. Go fly! Then come back and load the new log."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SIZE_BODY}px;
            background-color: {Colors.BG_SURFACE};
            border: 1px solid {Colors.BORDER_SUBTLE};
            border-radius: {Radius.MD}px;
            padding: {Spacing.MD}px;
        """)
        layout.addWidget(instructions)

    def on_enter(self):
        self._generate_recommendations()
        self._render_review()

    def can_proceed(self) -> bool:
        return True  # Always can proceed from export

    # ── Review UI ─────────────────────────────────────────────────

    def _build_step_response_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setSpacing(Spacing.SM)
        self._step_plots = {}
        for axis in ("roll", "pitch", "yaw"):
            plot = pg.PlotWidget()
            plot.setTitle(axis.capitalize())
            plot.setLabel("bottom", "Time (s)")
            plot.setLabel("left", "Normalized")
            plot.showGrid(x=True, y=True, alpha=0.2)
            plot.setDownsampling(auto=True, mode="peak")
            self._step_plots[axis] = plot
            layout.addWidget(plot)
        self.review_tabs.addTab(tab, "📈 Step Response")

    def _build_heatmap_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(Spacing.SM)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Axis:"))
        self._heatmap_axis_combo = QComboBox()
        self._heatmap_axis_combo.addItems(["roll", "pitch", "yaw"])
        self._heatmap_axis_combo.currentTextChanged.connect(self._render_heatmap)
        controls.addWidget(self._heatmap_axis_combo)
        controls.addStretch()
        layout.addLayout(controls)

        heatmap_plot_item = pg.PlotItem()
        heatmap_plot_item.setLabel("bottom", "Throttle (%)")
        heatmap_plot_item.setLabel("left", "Frequency (Hz)")
        heatmap_plot_item.setTitle("Throttle vs Noise")
        self._heatmap_view = pg.ImageView(view=heatmap_plot_item)
        self._heatmap_view.setColorMap(_make_thermal_colormap())
        layout.addWidget(self._heatmap_view)

        self.review_tabs.addTab(tab, "🔥 Noise Heatmap")

    def _render_review(self):
        analysis = self.state.analysis
        step_responses = analysis.step_responses if analysis else {}
        for axis, plot in self._step_plots.items():
            plot.clear()
            data = step_responses.get(axis)
            if not data:
                plot.setTitle(f"{axis.capitalize()} (no data)")
                continue
            plot.plot(data["t"], data["response"], pen=pg.mkPen("#42A5F5", width=2))
            plot.addItem(pg.InfiniteLine(pos=1.0, angle=0, pen=pg.mkPen("white", width=1,
                         style=Qt.PenStyle.DashLine)))
            title = axis.capitalize()
            if data.get("overshoot_pct") is not None:
                title += f"  ·  {data['overshoot_pct']:.0f}% overshoot"
            plot.setTitle(title)
        self._render_heatmap()

    def _render_heatmap(self):
        analysis = self.state.analysis
        heatmaps = analysis.heatmaps if analysis else {}
        axis = self._heatmap_axis_combo.currentText()
        data = heatmaps.get(axis)
        if data is None:
            return
        hm = data["heatmap"]
        tr = pg.QtGui.QTransform()
        tr.scale(100.0 / hm.shape[1], data["freq"][-1] / hm.shape[0])
        self._heatmap_view.setImage(hm, autoRange=False, transform=tr)
        self._heatmap_view.getView().setTitle(f"Throttle vs Noise — {axis.capitalize()}")

    # ── Recommendation generation ─────────────────────────────────

    def _generate_recommendations(self):
        """Display recommendations from the Prescription Engine (pre-computed)."""
        if not self.state.has_log:
            self.changes_label.setText("Load a log first to get recommendations.")
            return

        # Use pre-computed results from analysis if available
        if self.state.has_analysis and self.state.analysis.cli_diff:
            diff = self.state.analysis.cli_diff
        else:
            # Fallback: compute on the fly
            from fpv_tuner.core.diagnostics import run_diagnostics
            from fpv_tuner.core.prescription import generate_prescription
            from fpv_tuner.core.cli_diff import diff_from_prescription

            df = self.state.log.dataframe
            cli_settings = self.state.cli.settings if self.state.has_cli else None
            cli_version = self.state.cli.version if self.state.has_cli else None
            findings = run_diagnostics(df, cli_settings)
            prescription = generate_prescription(
                findings, cli_settings, cli_version=cli_version,
            )
            diff = diff_from_prescription(cli_settings, prescription)

        from fpv_tuner.core.cli_diff import format_diff_html, format_cli_commands
        from fpv_tuner.core.cli import get_schema

        cli_version = self.state.cli.version if self.state.has_cli else None
        schema = get_schema(cli_version)

        self._diff = diff
        self._schema = schema

        if not diff.has_changes:
            self.changes_label.setText(
                "✅  No critical changes needed — your quad looks good! "
                "The commands below are just a backup of your current settings."
            )
            self.cli_preview.setPlainText(
                "# No changes recommended\n"
                "# Your current configuration looks healthy.\n"
                "# Fly and log again to verify!"
            )
            return

        # Rich diff summary
        html = format_diff_html(diff)
        self.changes_label.setText(html)

        # CLI commands
        cli_text = format_cli_commands(diff, schema=schema)
        self.cli_preview.setPlainText(cli_text)

    # ── Actions ───────────────────────────────────────────────────

    def _copy_to_clipboard(self):
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.cli_preview.toPlainText())
        self.copy_btn.setText("✅  Copied!")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.copy_btn.setText("📋  Copy to Clipboard"))

    def _save_to_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CLI Commands", "fpv_tuner_changes.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if path:
            with open(path, "w") as f:
                f.write(self.cli_preview.toPlainText())
            self.save_btn.setText("✅  Saved!")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(2000, lambda: self.save_btn.setText("💾  Save to File"))

    # ── Write to FC ───────────────────────────────────────────────

    def _write_to_fc(self):
        if self._diff is None or not self._diff.has_changes:
            QMessageBox.information(
                self, "No Changes",
                "There are no recommended changes to write yet.",
            )
            return

        port = SerialPortDialog.get_port(self, "Write Changes to FC")
        if not port:
            return

        if self._jobs is None:
            QMessageBox.warning(self, "Not Available", "Background runner unavailable.")
            return

        # Only write changed/added entries (skip "removed" placeholders).
        changes = [
            e for e in self._diff.entries if e.kind in ("changed", "added")
        ]
        schema = self._schema

        self.write_btn.setEnabled(False)
        self.write_btn.setText("⏳  Writing...")

        def _run(job):
            from fpv_tuner.core.serial import write_changes_to_fc
            job.report_progress(30, "Connecting to FC...")
            return write_changes_to_fc(port, changes, schema=schema)

        self._jobs.run(
            fn=_run,
            on_result=self._on_write_done,
            on_error=self._on_write_error,
        )

    def _on_write_done(self, result):
        self._reset_write_btn()
        if result.success:
            QMessageBox.information(
                self, "Success",
                f"Applied {result.n_applied} change(s) to the flight controller.\n"
                "The FC will save and reboot.",
            )
        else:
            QMessageBox.warning(
                self, "Write Incomplete",
                "Some changes could not be applied:\n\n"
                + "\n".join(result.errors or ["Unknown error"]),
            )

    def _on_write_error(self, error_msg):
        self._reset_write_btn()
        QMessageBox.critical(
            self, "Write Failed",
            f"Could not write to the FC:\n\n{error_msg.splitlines()[-1] if error_msg else 'Unknown error'}",
        )

    def _reset_write_btn(self):
        self.write_btn.setEnabled(True)
        self.write_btn.setText("🛰  Write to FC")
