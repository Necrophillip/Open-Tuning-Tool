"""
Step 4 — Diagnosis.

Shows findings from the Diagnostics Engine in plain English,
ordered by severity. Each finding is a card: what it is, why it
matters, what to do.  Powered by fpv_tuner.core.diagnostics.
"""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget, QFrame,
)
from PyQt6.QtCore import Qt

from fpv_tuner.ui.pages.base_page import WizardPage
from fpv_tuner.ui.app_state import AppState
from fpv_tuner.ui.theme import Colors, Spacing, Radius, Typography
from fpv_tuner.ui.animations import reveal_cards


# ── Finding card widget ──────────────────────────────────────────

class FindingCard(QFrame):
    """A single finding displayed as an expandable card."""

    SEVERITY_CONFIG = {
        "critical": {"color": Colors.DANGER,  "bg": Colors.DANGER_MUTED,  "icon": "🔴", "label": "Critical"},
        "warning":  {"color": Colors.WARNING, "bg": Colors.WARNING_MUTED, "icon": "🟡", "label": "Warning"},
        "info":     {"color": Colors.ACCENT,  "bg": Colors.ACCENT_MUTED,  "icon": "🔵", "label": "Info"},
        "good":     {"color": Colors.SUCCESS, "bg": Colors.SUCCESS_MUTED, "icon": "✅", "label": "Looks Good"},
    }

    def __init__(self, severity: str, title: str, explanation: str,
                 recommendation: str = "", parent=None):
        super().__init__(parent)
        cfg = self.SEVERITY_CONFIG.get(severity, self.SEVERITY_CONFIG["info"])

        self.setStyleSheet(f"""
            FindingCard {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-left: 3px solid {cfg['color']};
                border-radius: {Radius.MD}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        layout.setSpacing(Spacing.SM)

        # Header row
        header = QHBoxLayout()
        badge = QLabel(f"{cfg['icon']}  {cfg['label']}")
        badge.setStyleSheet(f"""
            color: {cfg['color']};
            font-size: {Typography.SIZE_CAPTION}px;
            font-weight: 700;
            background: {cfg['bg']};
            padding: 2px 8px;
            border-radius: {Radius.SM}px;
        """)
        header.addWidget(badge)
        header.addStretch()
        layout.addLayout(header)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: {Typography.SIZE_HEADING}px;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # Explanation
        expl_label = QLabel(explanation)
        expl_label.setWordWrap(True)
        expl_label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SIZE_BODY}px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(expl_label)

        # Recommendation (if any)
        if recommendation:
            rec_label = QLabel(f"💡  {recommendation}")
            rec_label.setWordWrap(True)
            rec_label.setStyleSheet(f"""
                color: {Colors.ACCENT};
                font-size: {Typography.SIZE_BODY}px;
                background: {Colors.ACCENT_MUTED};
                padding: {Spacing.SM}px;
                border-radius: {Radius.SM}px;
                border: none;
            """)
            layout.addWidget(rec_label)


# ── Diagnosis page ───────────────────────────────────────────────

class DiagnosisPage(WizardPage):
    STEP_TITLE = "Diagnosis"
    STEP_SUBTITLE = "What we found in your log"

    def __init__(self, state: AppState, job_runner, parent=None):
        self._jobs = job_runner
        super().__init__(state, parent)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        layout.addWidget(self._make_title("Diagnosis"))
        layout.addWidget(self._make_subtitle(
            "Here's what we found in your flight data, "
            "explained in plain English."
        ))

        # Scrollable findings area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.findings_container = QWidget()
        self.findings_layout = QVBoxLayout(self.findings_container)
        self.findings_layout.setSpacing(Spacing.MD)
        self.findings_layout.setContentsMargins(0, 0, 0, Spacing.XL)
        self.findings_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.findings_container)
        layout.addWidget(scroll, 1)

    def on_enter(self):
        if self.state.has_log:
            self._generate_findings()

    def can_proceed(self) -> bool:
        return self.state.has_analysis

    # ── Findings generation (Sprint 2: Diagnostics Engine) ──────

    def _generate_findings(self):
        """Display findings from the Diagnostics Engine (pre-computed by Analysis page)."""
        from fpv_tuner.core.diagnostics import Severity

        # Clear old findings
        while self.findings_layout.count() > 0:
            item = self.findings_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Use pre-computed findings from analysis if available
        if self.state.has_analysis and self.state.analysis.findings:
            engine_findings = self.state.analysis.findings
        else:
            # Fallback: run diagnostics on the fly
            from fpv_tuner.core.diagnostics import run_diagnostics
            df = self.state.log.dataframe
            cli_settings = self.state.cli.settings if self.state.has_cli else None
            engine_findings = run_diagnostics(df, cli_settings)

        # Count by severity
        n_critical = sum(1 for f in engine_findings if f.severity == Severity.CRITICAL)
        n_warning = sum(1 for f in engine_findings if f.severity == Severity.WARNING)

        # Overall summary card
        if n_critical == 0 and n_warning == 0:
            summary_card = FindingCard(
                "good",
                "Overall: Your quad looks healthy! 🎉",
                "No critical noise issues detected in this log. "
                "The gyro signal is clean and filters appear effective.",
                "",
            )
        else:
            issues = []
            if n_critical:
                issues.append(f"{n_critical} critical issue{'s' if n_critical > 1 else ''}")
            if n_warning:
                issues.append(f"{n_warning} warning{'s' if n_warning > 1 else ''}")
            summary_card = FindingCard(
                "warning",
                f"Overall: Found {' and '.join(issues)}",
                "Review the findings below and apply the recommendations "
                "in the next step.",
                "",
            )

        self.findings_layout.addWidget(summary_card)

        # Add finding cards
        all_cards = [summary_card]
        for f in engine_findings:
            card = FindingCard(
                f.severity.value,
                f.title,
                f.explanation,
                f.recommendation,
            )
            self.findings_layout.addWidget(card)
            all_cards.append(card)

        # Stagger reveal animation
        reveal_cards(all_cards, stagger_ms=60)

    # Old heuristic methods removed — now using fpv_tuner.core.diagnostics
