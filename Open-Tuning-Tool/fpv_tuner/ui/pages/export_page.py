"""
Step 4 — Export / Review.

Shows the analysis summary (step responses + noise heatmaps) front and
center, a compact summary of the recommended changes, and actions to
apply them (write to FC / copy / show the generated CLI commands).
"""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit,
    QMessageBox, QWidget, QComboBox, QDialog,
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
        from PyQt6.QtWidgets import QScrollArea, QFrame, QWidget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; } QWidget#scroll_content { background: transparent; }")
        
        content = QWidget()
        content.setObjectName("scroll_content")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        layout.setSpacing(Spacing.SM)
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        layout.addWidget(self._make_title("Export & Apply"))
        layout.addWidget(self._make_subtitle(
            "Review the analysis, then apply the recommended changes to your quad."
        ))

        # ── Step response (3 axes) ─────────────────────────────────
        layout.addWidget(_section_label("📈  Step Response"))
        step_row = QHBoxLayout()
        step_row.setSpacing(Spacing.SM)
        self._step_plots = {}
        for axis in ("roll", "pitch", "yaw"):
            plot = pg.PlotWidget()
            plot.setTitle(axis.capitalize())
            plot.setLabel("bottom", "Time (s)")
            plot.setLabel("left", "Normalized")
            plot.showGrid(x=True, y=True, alpha=0.2)
            plot.setDownsampling(auto=True, mode="peak")
            self._step_plots[axis] = plot
            step_row.addWidget(plot)
        layout.addLayout(step_row, 2)

        # ── Gyro Noise Heatmap ─────────────────────────────────────
        layout.addWidget(_section_label("🔥 Gyro Noise Heatmap"))
        gyro_row = QHBoxLayout()
        gyro_row.setSpacing(Spacing.SM)
        self._gyro_views = {}
        for axis in ("roll", "pitch", "yaw"):
            plot_item = pg.PlotItem(title="")
            plot_item.setLabel("bottom", "Throttle (%)")
            plot_item.setLabel("left", "Frequency (Hz)")
            view = pg.ImageView(view=plot_item)
            view.setColorMap(_make_thermal_colormap())
            view.ui.histogram.hide()
            view.ui.roiBtn.hide()
            view.ui.menuBtn.hide()
            view.setMinimumHeight(200)
            view.getView().invertY(False)
            self._gyro_views[axis] = view
            gyro_row.addWidget(view)
        layout.addLayout(gyro_row, 2)

        # ── D-Term Noise Heatmap ───────────────────────────────────
        layout.addWidget(_section_label("🔥 D-Term Noise Heatmap"))
        dterm_row = QHBoxLayout()
        dterm_row.setSpacing(Spacing.SM)
        self._dterm_views = {}
        for axis in ("roll", "pitch", "yaw"):
            plot_item = pg.PlotItem(title="")
            plot_item.setLabel("bottom", "Throttle (%)")
            plot_item.setLabel("left", "Frequency (Hz)")
            view = pg.ImageView(view=plot_item)
            view.setColorMap(_make_thermal_colormap())
            view.ui.histogram.hide()
            view.ui.roiBtn.hide()
            view.ui.menuBtn.hide()
            view.setMinimumHeight(200)
            view.getView().invertY(False)
            self._dterm_views[axis] = view
            dterm_row.addWidget(view)
        layout.addLayout(dterm_row, 2)

        # ── RPM Filter Harmonics ───────────────────────────────────
        layout.addWidget(_section_label("🎵 RPM Filter Harmonics"))
        harm_row = QHBoxLayout()
        harm_row.setSpacing(Spacing.SM)
        self._harm_plots = {}
        for axis in ("roll", "pitch", "yaw"):
            plot = pg.PlotWidget()
            plot.setTitle(axis.capitalize())
            plot.setLabel("bottom", "Throttle (%)")
            plot.setLabel("left", "Frequency (Hz)")
            plot.showGrid(x=True, y=True, alpha=0.2)
            plot.setMinimumHeight(200)
            self._harm_plots[axis] = plot
            harm_row.addWidget(plot)
        layout.addLayout(harm_row, 2)

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
            plot.plot(data["t"], data["response"], pen=pg.mkPen("#42A5F5", width=2))
            plot.addItem(pg.InfiniteLine(pos=1.0, angle=0, pen=pg.mkPen("white", width=1,
                         style=Qt.PenStyle.DashLine)))
            title = axis.capitalize()
            if data.get("overshoot_pct") is not None:
                title += f"  ·  {data['overshoot_pct']:.0f}% overshoot"
            plot.setTitle(title)
            
        gyro_heatmaps = getattr(analysis, "heatmaps", {})
        dterm_heatmaps = getattr(analysis, "dterm_heatmaps", {})
        
        self._update_heatmaps(self._gyro_views, gyro_heatmaps)
        self._update_heatmaps(self._dterm_views, dterm_heatmaps)
        self._render_harmonics(self._harm_plots, gyro_heatmaps)

    def _update_heatmaps(self, views, heatmaps):
        for axis, view in views.items():
            view.getView().clear()
            data = heatmaps.get(axis)
            if not data:
                view.getView().setTitle(f"{axis.capitalize()} (No data)")
                view.clear()
                continue
                
            view.getView().setTitle("")
            hm = data["heatmap"]
            img = hm.T
            freq_max = data["freq"][-1]
            
            tr = pg.QtGui.QTransform()
            tr.scale(100.0 / img.shape[0], freq_max / img.shape[1])
            
            v_min, v_max = np.nanmin(img), np.nanpercentile(img, 99.5)
            if np.isnan(v_max) or v_min == v_max: v_max = v_min + 1
            
            view.setImage(img, autoRange=False, levels=(v_min, v_max), transform=tr)
            
            mean_val = np.nanmean(img)
            peak_val = np.nanmax(img)
            
            axis_label = pg.TextItem(axis, color=(255, 255, 255), anchor=(0, 0))
            axis_label.setPos(2, freq_max - (freq_max * 0.05))
            view.getView().addItem(axis_label)
            
            stats_label = pg.TextItem(f"mean={mean_val:.3f}\npeak={peak_val:.3f}", color=(255, 255, 255), anchor=(1, 0))
            stats_label.setPos(98, freq_max - (freq_max * 0.05))
            view.getView().addItem(stats_label)
            
            view.getView().setLimits(xMin=0, xMax=100, yMin=0, yMax=freq_max)
            view.getView().setXRange(0, 100, padding=0)
            view.getView().setYRange(0, freq_max, padding=0)
            
            x_ax = view.getView().getAxis("bottom")
            x_ax.setTicks([[(i, str(i)) for i in range(0, 101, 20)]])
            y_ax = view.getView().getAxis("left")
            y_ax.setTicks([[(i, str(i)) for i in range(0, int(freq_max) + 1, 200)]])

    def _render_harmonics(self, plots, heatmaps):
        for axis, plot in plots.items():
            plot.clear()
            data = heatmaps.get(axis)
            if not data or "h1" not in data:
                plot.setTitle(f"{axis.capitalize()} (No data)")
                continue
                
            plot.setTitle(f"{axis.capitalize()}")
            tc = data["throttle"]
            colors = ["#00ffff", "#ffaa00", "#ffff00"]
            names = ["H1 (Fundamental)", "H2 (2x)", "H3 (3x)"]
            
            for i, h_key in enumerate(["h1", "h2", "h3"]):
                if h_key in data:
                    plot.plot(tc, data[h_key], name=names[i], pen=pg.mkPen(colors[i], width=2))
                    
            freq_max = data["freq"][-1]
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
