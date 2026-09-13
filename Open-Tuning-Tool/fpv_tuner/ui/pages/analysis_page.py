"""
Step 3 — Automatic Analysis.

Runs all analysis passes (noise PSD, spectrogram, throttle heatmap,
filter comparison) in background threads and shows live progress.
"""
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, QTimer

from fpv_tuner.ui.pages.base_page import WizardPage
from fpv_tuner.ui.app_state import AppState, AnalysisResult
from fpv_tuner.ui.theme import Colors, Spacing, Typography


class _AnalysisTask:
    """One row in the analysis checklist."""
    def __init__(self, label: str):
        self.label = label
        self.status = "pending"   # pending | running | done | error
        self.detail = ""


class AnalysisPage(WizardPage):
    STEP_TITLE = "Analysis"
    STEP_SUBTITLE = "Automatic noise and filter analysis"

    TASKS = [
        "Gyro noise floor",
        "Pre/Post filter comparison",
        "Throttle vs noise heatmap",
        "Signal statistics",
    ]

    def __init__(self, state: AppState, job_runner, parent=None):
        self._jobs = job_runner
        self._tasks = [_AnalysisTask(t) for t in self.TASKS]
        self._task_labels = []
        self._running = False
        super().__init__(state, parent)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        layout.addWidget(self._make_title("Analyzing your log"))
        layout.addWidget(self._make_subtitle(
            "Sit tight — we're running a full noise and filter analysis "
            "on your flight data. This usually takes a few seconds."
        ))

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # Task checklist
        tasks_container = QVBoxLayout()
        tasks_container.setSpacing(Spacing.SM)
        for task in self._tasks:
            row = QHBoxLayout()
            row.setSpacing(Spacing.MD)

            status_icon = QLabel("⏳")
            status_icon.setFixedWidth(24)
            status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

            task_label = QLabel(task.label)
            task_label.setStyleSheet(f"""
                color: {Colors.TEXT_SECONDARY};
                font-size: {Typography.SIZE_BODY}px;
            """)

            detail_label = QLabel("")
            detail_label.setStyleSheet(f"""
                color: {Colors.TEXT_DISABLED};
                font-size: {Typography.SIZE_CAPTION}px;
            """)

            row.addWidget(status_icon)
            row.addWidget(task_label, 1)
            row.addWidget(detail_label)
            tasks_container.addLayout(row)

            self._task_labels.append({
                "icon": status_icon,
                "label": task_label,
                "detail": detail_label,
            })

        layout.addLayout(tasks_container)
        layout.addStretch()

        # Summary card (shown when done)
        self.summary_card = QLabel("")
        self.summary_card.setWordWrap(True)
        self.summary_card.hide()
        layout.addWidget(self.summary_card)

    # ── Analysis execution ────────────────────────────────────────

    def on_enter(self):
        if self.state.has_analysis:
            self._show_completed()
            return
        if self.state.has_log and not self._running:
            self._start_analysis()

    def _start_analysis(self):
        self._running = True
        self.progress.setValue(0)

        for i, labels in enumerate(self._task_labels):
            self._set_task_status(i, "pending")

        df = self.state.log.dataframe

        def _run_all(job):
            results = {}
            total = len(self.TASKS)

            # Task 1: Gyro noise floor
            job.report_progress(5, "Computing gyro noise floor...")
            results["gyro"] = self._analyze_gyro(df)
            job.report_progress(25, "Gyro analysis complete")

            # Task 2: Pre/Post filter
            job.report_progress(30, "Comparing pre/post filter...")
            results["filter"] = self._analyze_filter(df)
            job.report_progress(55, "Filter comparison complete")

            # Task 3: Throttle heatmap
            job.report_progress(60, "Building throttle heatmap...")
            results["heatmap"] = self._analyze_heatmap(df)
            job.report_progress(85, "Heatmap complete")

            # Task 4: Statistics
            job.report_progress(90, "Computing statistics...")
            results["stats"] = self._analyze_stats(df)
            job.report_progress(100, "Analysis complete")

            return results

        self._jobs.run(
            fn=_run_all,
            on_result=self._on_analysis_done,
            on_error=self._on_analysis_error,
            on_progress=self._on_progress,
        )

    def _analyze_gyro(self, df):
        from fpv_tuner.analysis.noise import (
            get_sampling_frequency, calculate_psd, calculate_signal_stats
        )
        result = {}
        time_col = next((c for c in df.columns if "time" in c.lower() and "us" in c.lower()), None)
        if not time_col:
            return {"error": "No time column found"}

        fs = get_sampling_frequency(df[time_col])
        result["sampling_hz"] = fs

        for axis in range(3):
            col = f"gyroADC[{axis}]"
            if col in df.columns:
                freqs, psd = calculate_psd(df[col], df[time_col])
                if freqs is not None and psd is not None:
                    stats = calculate_signal_stats(df[col], freqs, psd)
                    result[f"axis_{axis}"] = {
                        "freq_points": len(freqs),
                        "rms": stats.get("RMS", "N/A"),
                        "peak_hz": freqs[psd.argmax()] if len(psd) > 0 else 0,
                    }
        return result

    def _analyze_filter(self, df):
        from fpv_tuner.analysis.noise import calculate_pre_post_filter_psd
        time_col = next((c for c in df.columns if "time" in c.lower() and "us" in c.lower()), None)
        if not time_col:
            return {"error": "No time column"}

        result = {}
        for axis in range(3):
            data = calculate_pre_post_filter_psd(df, time_col, axis)
            if data and data.get("psd_pre") is not None:
                result[f"axis_{axis}"] = {
                    "freq_points": len(data["freq"]),
                }
        return result

    def _analyze_heatmap(self, df):
        from fpv_tuner.analysis.noise import calculate_throttle_noise_heatmap
        import numpy as np
        import pandas as pd

        time_col = next((c for c in df.columns if "time" in c.lower() and "us" in c.lower()), None)
        noise_col = "gyroADC[0]"
        throttle_col = next(
            (c for c in df.columns if "rccommand" in c.lower() and "3" in c),
            None
        ) or "motor[0]"

        if not all(c in df.columns for c in [time_col, noise_col, throttle_col]):
            return {"error": "Missing columns"}

        raw = df[throttle_col].astype(float)
        mn, mx = raw.min(), raw.max()
        if mx > mn:
            throttle = (raw - mn) / (mx - mn) * 100.0
        else:
            throttle = pd.Series(np.full(len(raw), 50.0), index=raw.index)

        nperseg = min(256, len(df) // 4)
        tc, fb, hm = calculate_throttle_noise_heatmap(
            df[noise_col], throttle, df[time_col],
            n_throttle_bins=20, n_freq_bins=64, nperseg=nperseg,
        )
        if tc is not None:
            return {
                "shape": f"{hm.shape[0]}×{hm.shape[1]}",
                "range_db": f"{np.nanmin(hm):.1f} to {np.nanmax(hm):.1f}",
            }
        return {"error": "Insufficient data"}

    def _analyze_stats(self, df):
        from fpv_tuner.analysis.noise import calculate_psd, calculate_signal_stats
        result = {}
        time_col = next((c for c in df.columns if "time" in c.lower() and "us" in c.lower()), None)
        if not time_col:
            return {"error": "No time column"}
        for col_name, label in [("gyroADC[0]", "roll"), ("gyroADC[1]", "pitch"), ("gyroADC[2]", "yaw")]:
            if col_name in df.columns:
                freqs, psd = calculate_psd(df[col_name], df[time_col])
                stats = calculate_signal_stats(df[col_name], freqs, psd)
                result[label] = stats
        return result

    # ── Callbacks ─────────────────────────────────────────────────

    def _on_progress(self, pct, msg):
        self.progress.setValue(pct)
        # Update task icons based on progress
        thresholds = [25, 55, 85, 100]
        for i, threshold in enumerate(thresholds):
            if pct >= threshold:
                self._set_task_status(i, "done")
            elif pct >= (thresholds[i-1] if i > 0 else 0):
                self._set_task_status(i, "running")

    def _on_analysis_done(self, results):
        self._running = False
        for i in range(len(self._tasks)):
            self._set_task_status(i, "done")

        # Build summary
        summary_parts = []
        gyro = results.get("gyro", {})
        if "sampling_hz" in gyro:
            summary_parts.append(f"Sampling rate: {gyro['sampling_hz']:.0f} Hz")
        for axis_name in ["roll", "pitch", "yaw"]:
            stats = results.get("stats", {}).get(axis_name, {})
            if "RMS" in stats:
                summary_parts.append(f"{axis_name.capitalize()} RMS: {stats['RMS']}")

        # Sprint 2: run diagnostics + prescription engine
        engine_findings = []
        prescription = None
        cli_diff = None
        session_id = ""

        if self.state.has_log:
            from fpv_tuner.core.diagnostics import run_diagnostics, Severity
            from fpv_tuner.core.prescription import generate_prescription
            from fpv_tuner.core.cli_diff import diff_from_prescription
            from fpv_tuner.core.session_history import build_snapshot, save_session

            df = self.state.log.dataframe
            cli_settings = self.state.cli.settings if self.state.has_cli else None

            engine_findings = run_diagnostics(df, cli_settings)
            prescription = generate_prescription(engine_findings, cli_settings)
            cli_diff = diff_from_prescription(cli_settings, prescription)

            # Count issues for summary
            n_crit = sum(1 for f in engine_findings if f.severity == Severity.CRITICAL)
            n_warn = sum(1 for f in engine_findings if f.severity == Severity.WARNING)
            if n_crit or n_warn:
                summary_parts.append(f"{n_crit} critical, {n_warn} warnings")
            else:
                summary_parts.append("No issues found")

            # Save session
            snap = build_snapshot(
                log_file=self.state.log.file_path,
                findings=engine_findings,
                prescription=prescription,
                cli_version=self.state.cli.version if self.state.has_cli else "",
                n_rows=len(df),
                duration_s=self.state.log.duration_s,
            )
            session_id = save_session(snap)

        summary = "  •  ".join(summary_parts) if summary_parts else "Analysis complete."

        self.summary_card.setText(f"✅  {summary}")
        self.summary_card.setStyleSheet(f"""
            background-color: {Colors.SUCCESS_MUTED};
            color: {Colors.SUCCESS};
            border: 1px solid {Colors.SUCCESS};
            border-radius: 10px;
            padding: {Spacing.MD}px;
            font-size: {Typography.SIZE_BODY}px;
        """)
        self.summary_card.show()

        self.state.set_analysis(AnalysisResult(
            completed=True,
            summary=summary,
            findings=engine_findings,
            prescription=prescription,
            cli_diff=cli_diff,
            session_id=session_id,
        ))
        self.validity_changed.emit()

    def _on_analysis_error(self, error_msg):
        self._running = False
        self.summary_card.setText(f"❌  Analysis failed: {error_msg.splitlines()[-1]}")
        self.summary_card.setStyleSheet(f"""
            background-color: {Colors.DANGER_MUTED};
            color: {Colors.DANGER};
            border: 1px solid {Colors.DANGER};
            border-radius: 10px;
            padding: {Spacing.MD}px;
        """)
        self.summary_card.show()

    def _show_completed(self):
        for i in range(len(self._tasks)):
            self._set_task_status(i, "done")
        self.progress.setValue(100)
        if self.state.analysis:
            self.summary_card.setText(f"✅  {self.state.analysis.summary}")
            self.summary_card.setStyleSheet(f"""
                background-color: {Colors.SUCCESS_MUTED};
                color: {Colors.SUCCESS};
                border: 1px solid {Colors.SUCCESS};
                border-radius: 10px;
                padding: {Spacing.MD}px;
            """)
            self.summary_card.show()

    def _set_task_status(self, index: int, status: str):
        icons = {"pending": "⏳", "running": "🔄", "done": "✅", "error": "❌"}
        colors = {
            "pending": Colors.TEXT_DISABLED,
            "running": Colors.ACCENT,
            "done": Colors.SUCCESS,
            "error": Colors.DANGER,
        }
        labels = self._task_labels[index]
        labels["icon"].setText(icons.get(status, "⏳"))
        labels["label"].setStyleSheet(f"""
            color: {colors.get(status, Colors.TEXT_SECONDARY)};
            font-size: {Typography.SIZE_BODY}px;
        """)
        self._tasks[index].status = status

    # ── Contract ──────────────────────────────────────────────────

    def can_proceed(self) -> bool:
        return self.state.has_analysis
