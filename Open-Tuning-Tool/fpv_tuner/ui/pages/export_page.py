"""
Step 4 — Export / Review.

Shows the analysis summary (step responses + noise heatmaps) front and
center, a compact summary of the recommended changes, and actions to
apply them (write to FC / copy / show the generated CLI commands).
"""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit,
    QMessageBox, QWidget, QComboBox, QDialog, QTabWidget,
)
from PyQt6.QtCore import Qt

import pyqtgraph as pg
import numpy as np

from fpv_tuner.ui.pages.base_page import WizardPage
from fpv_tuner.ui.app_state import AppState
from fpv_tuner.ui.widgets.serial_port_dialog import SerialPortDialog
from fpv_tuner.ui.theme import Colors, Spacing, Radius, Typography


def _make_thermal_colormap():
    positions = [0.0, 0.25, 0.5, 0.75, 1.0]
    colors = [
        (0, 0, 0),        # Black
        (128, 0, 0),      # Dark Red
        (255, 100, 0),    # Orange
        (255, 255, 0),    # Yellow
        (255, 255, 255)   # White
    ]
    return pg.ColorMap(positions, colors)


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"""
        color: {Colors.TEXT_PRIMARY};
        font-size: {Typography.SIZE_HEADING}px;
        font-weight: 600;
    """)
    return label


class ExportPage(WizardPage):
    STEP_TITLE = "Export"
    STEP_SUBTITLE = "Review & apply your new configuration"

    def __init__(self, state: AppState, job_runner=None, parent=None):
        self._jobs = job_runner
        self._diff = None
        self._schema = None
        self._cli_text = ""
        super().__init__(state, parent)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        layout.setSpacing(Spacing.SM)

        layout.addWidget(self._make_title("Export & Apply"))
        layout.addWidget(self._make_subtitle(
            "Review the analysis, then apply the recommended changes to your quad."
        ))

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        # Tab 1: Step Response
        step_tab = QWidget()
        step_layout = QHBoxLayout(step_tab)
        step_layout.setSpacing(Spacing.SM)
        self._step_plots = {}
        for axis in ("roll", "pitch", "yaw"):
            plot = pg.PlotWidget(title=axis.capitalize())
            plot.setLabel("bottom", "Time (s)")
            plot.setLabel("left", "Normalized")
            plot.showGrid(x=True, y=True, alpha=0.2)
            plot.setDownsampling(auto=True, mode="peak")
            plot.addLegend(offset=(10, 10))
            self._step_plots[axis] = plot
            step_layout.addWidget(plot)
        self.tabs.addTab(step_tab, "📈 Step Response")

        # Helper for Tabs 2 & 3
        def _make_heatmap_tab(label):
            tab = QWidget()
            t_layout = QHBoxLayout(tab)
            t_layout.setSpacing(Spacing.SM)
            views = {}
            for axis in ("roll", "pitch", "yaw"):
                plot = pg.PlotWidget(title=axis.capitalize())
                plot.setLabel("bottom", "Throttle (%)")
                plot.setLabel("left", "Frequency (Hz)")
                plot.showGrid(x=True, y=True, alpha=0.2)
                img = pg.ImageItem()
                img.setColorMap(_make_thermal_colormap())
                plot.addItem(img)
                views[axis] = (plot, img)
                t_layout.addWidget(plot)
            self.tabs.addTab(tab, label)
            return views

        self._gyro_views = _make_heatmap_tab("🔥 Gyro Noise")
        self._dterm_views = _make_heatmap_tab("🔥 D-Term Noise")

        # ── Changes summary (compact) ──────────────────────────────
        self.changes_label = QLabel("No changes recommended yet.")
        self.changes_label.setTextFormat(Qt.TextFormat.RichText)
        self.changes_label.setWordWrap(True)
        self.changes_label.setMaximumHeight(90)
        self.changes_label.setStyleSheet(f"""
            background-color: {Colors.BG_SURFACE};
            border: 1px solid {Colors.BORDER_SUBTLE};
            border-radius: {Radius.MD}px;
            padding: {Spacing.SM}px;
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SIZE_CAPTION}px;
        """)
        layout.addWidget(self.changes_label)

        # ── Action buttons ─────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(Spacing.MD)

        self.write_btn = QPushButton("✅  Apply to FC")
        self.write_btn.setProperty("variant", "primary")
        self.write_btn.setToolTip(
            "Connect the FC via USB and apply these CLI changes directly."
        )
        self.write_btn.clicked.connect(self._write_to_fc)
        btn_layout.addWidget(self.write_btn)

        self.show_cli_btn = QPushButton("🖥  Show CLI")
        self.show_cli_btn.setProperty("variant", "ghost")
        self.show_cli_btn.clicked.connect(self._show_cli_popup)
        btn_layout.addWidget(self.show_cli_btn)

        self.copy_btn = QPushButton("📋  Copy to Clipboard")
        self.copy_btn.setProperty("variant", "ghost")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        btn_layout.addWidget(self.copy_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def on_enter(self):
        self._generate_recommendations()
        self._render_review()

    def can_proceed(self) -> bool:
        return True

    def _render_review(self):
        analysis = self.state.analysis
        if not analysis:
            return
            
        step_responses = analysis.step_responses if analysis else {}
        for axis, plot in self._step_plots.items():
            plot.clear()
            data = step_responses.get(axis)
            if not data:
                plot.setTitle(f"{axis.capitalize()} (no data)")
                continue
            # 1. Y=1 Target Reference Line (native plot trace so it gets a legend entry)
            t_min, t_max = data["t"][0], data["t"][-1]
            plot.plot([t_min, t_max], [1.0, 1.0], name="Target", pen=pg.mkPen("#00E676", width=1, style=Qt.PenStyle.DashLine))
            
            # 2. RC Command (Setpoint)
            if "setpoint" in data:
                plot.plot(data["t"], data["setpoint"], name="RC Cmd", pen=pg.mkPen(color=(255, 255, 255, 120), width=1, style=Qt.PenStyle.DotLine))
                
            # 3. Response Signal
            plot.plot(data["t"], data["response"], name="Response", pen=pg.mkPen("#FF9100", width=2))
            
            # 4. Clean HTML Title
            sys_type = data.get('type', 'Unknown')
            os_pct = data.get('overshoot_pct', 0)
            title = (
                f"<div style='text-align: center;'>"
                f"<span style='color: #FFFFFF; font-size: 12pt; font-weight: bold;'>{axis.upper()}</span><br>"
                f"<span style='color: #B0BEC5; font-size: 9pt;'>"
                f"{sys_type} | OS: {os_pct:.0f}% | Rise: {data.get('rise_time_ms', 0):.0f}ms | Dly: {data.get('delay_ms', 0):.0f}ms"
                f"</span></div>"
            )
            plot.setTitle(title)
            
        gyro_heatmaps = getattr(analysis, "heatmaps", {})
        dterm_heatmaps = getattr(analysis, "dterm_heatmaps", {})
        
        self._update_heatmaps(self._gyro_views, gyro_heatmaps)
        self._update_heatmaps(self._dterm_views, dterm_heatmaps)

    def _update_heatmaps(self, views, heatmaps):
        for axis, (plot, img) in views.items():
            for item in plot.listDataItems():
                plot.removeItem(item)
                
            data = heatmaps.get(axis)
            if not data:
                plot.setTitle(f"{axis.capitalize()} (No data)")
                img.clear()
                continue
                
            plot.setTitle(axis.capitalize())
            hm = data["heatmap"]
            img_data = hm.T
            freq_max = data["freq"][-1]
            
            v_min, v_max = np.nanmin(img_data), np.nanpercentile(img_data, 99.5)
            if np.isnan(v_max) or v_min == v_max: v_max = v_min + 1
            
            img.setImage(img_data, autoLevels=False, levels=(v_min, v_max))
            img.setRect(pg.QtCore.QRectF(0, 0, 100.0, freq_max))
            
            # Overlay harmonics
            colors = ["#00ffff", "#ffaa00", "#ffff00"]
            for i, h in enumerate(["h1", "h2", "h3"]):
                if h in data:
                    plot.plot(data["throttle"], data[h], pen=pg.mkPen(colors[i], width=2, style=Qt.PenStyle.DashLine))
                    
            plot.setLimits(xMin=0, xMax=100, yMin=0, yMax=freq_max)
            plot.setXRange(0, 100, padding=0)
            plot.setYRange(0, freq_max, padding=0)

    # ── Recommendation generation ─────────────────────────────────

    def _generate_recommendations(self):
        """Display recommendations from the Prescription Engine (pre-computed)."""
        if not self.state.has_log:
            self.changes_label.setText("Load a log first to get recommendations.")
            self._cli_text = ""
            return

        # Use pre-computed results from analysis if available
        if self.state.has_analysis and self.state.analysis.cli_diff:
            diff = self.state.analysis.cli_diff
        else:
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
            
            if getattr(self.state, "tuning_recommendation", None) is not None:
                prescription.changes.update(self.state.tuning_recommendation.prescription.changes)
                
            diff = diff_from_prescription(cli_settings, prescription)

        from fpv_tuner.core.cli_diff import format_diff_html, format_cli_commands
        from fpv_tuner.core.cli import get_schema

        cli_version = self.state.cli.version if self.state.has_cli else None
        schema = get_schema(cli_version)

        self._diff = diff
        self._schema = schema

        if not diff.has_changes:
            self.changes_label.setText(
                "✅  No critical changes needed — your quad looks good!"
            )
            self._cli_text = (
                "# No changes recommended\n"
                "# Your current configuration looks healthy.\n"
                "# Fly and log again to verify!\n"
            )
            return

        self.changes_label.setText(format_diff_html(diff))
        self._cli_text = format_cli_commands(diff, schema=schema)

    # ── Actions ───────────────────────────────────────────────────

    def _show_cli_popup(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("CLI Commands")
        dialog.setMinimumSize(560, 480)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.MD)

        hint = QLabel(
            "Paste these commands into the Betaflight CLI (or use "
            "'Apply to FC' to write them directly)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Typography.SIZE_BODY}px;")
        layout.addWidget(hint)

        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(self._cli_text or "# No changes yet")
        editor.setStyleSheet(f"""
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
        layout.addWidget(editor, 1)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("📋  Copy")
        copy_btn.setProperty("variant", "ghost")
        copy_btn.clicked.connect(lambda: self._copy_text_to_clipboard(editor.toPlainText()))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.exec()

    def _copy_to_clipboard(self):
        self._copy_text_to_clipboard(self._cli_text)
        self.copy_btn.setText("✅  Copied!")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.copy_btn.setText("📋  Copy to Clipboard"))

    @staticmethod
    def _copy_text_to_clipboard(text: str):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    # ── Write to FC ───────────────────────────────────────────────

    def _write_to_fc(self):
        if self._diff is None or not self._diff.has_changes:
            QMessageBox.information(
                self, "No Changes",
                "There are no recommended changes to write yet.",
            )
            return

        port = SerialPortDialog.get_port(self, "Apply Changes to FC")
        if not port:
            return

        if self._jobs is None:
            QMessageBox.warning(self, "Not Available", "Background runner unavailable.")
            return

        changes = [e for e in self._diff.entries if e.kind in ("changed", "added")]
        schema = self._schema

        self.write_btn.setEnabled(False)
        self.write_btn.setText("⏳  Applying...")

        def _run(job):
            from fpv_tuner.core.serial import write_changes_to_fc
            job.report_progress(5, "Connecting to FC...")
            
            def on_progress(pct, msg):
                job.report_progress(5 + int(pct * 0.95), msg)
                
            return write_changes_to_fc(port, changes, schema=schema, progress_cb=on_progress)

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
                self, "Apply Incomplete",
                "Some changes could not be applied:\n\n"
                + "\n".join(result.errors or ["Unknown error"]),
            )

    def _on_write_error(self, error_msg):
        self._reset_write_btn()
        QMessageBox.critical(
            self, "Apply Failed",
            f"Could not write to the FC:\n\n{error_msg.splitlines()[-1] if error_msg else 'Unknown error'}",
        )

    def _reset_write_btn(self):
        self.write_btn.setEnabled(True)
        self.write_btn.setText("✅  Apply to FC")
