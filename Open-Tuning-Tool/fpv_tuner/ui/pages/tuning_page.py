from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget, QFrame,
)
from PyQt6.QtCore import Qt

from fpv_tuner.ui.pages.base_page import WizardPage
from fpv_tuner.ui.app_state import AppState
from fpv_tuner.ui.theme import Colors, Spacing, Radius, Typography
from fpv_tuner.ui.animations import reveal_cards


class RecommendationCard(QFrame):
    """A card showing a PID tuning recommendation."""

    def __init__(self, kind: str, reasoning: str, changes: dict, rule_status: str, safety_flags: list, parent=None):
        super().__init__(parent)
        
        is_heuristic = "heuristic" in rule_status.lower()
        border_color = Colors.ACCENT if is_heuristic else Colors.SUCCESS
        bg_color = Colors.ACCENT_MUTED if is_heuristic else Colors.SUCCESS_MUTED
        icon = "🧠" if is_heuristic else "✅"

        self.setStyleSheet(f"""
            RecommendationCard {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-left: 3px solid {border_color};
                border-radius: {Radius.MD}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        layout.setSpacing(Spacing.SM)

        # Header row
        header = QHBoxLayout()
        title = QLabel(f"{icon}  {kind.replace('_', ' ').title()}")
        title.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: {Typography.SIZE_HEADING}px;
            font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()

        status_badge = QLabel(f"  {rule_status.replace('_', ' ').title()}  ")
        status_badge.setStyleSheet(f"""
            color: {border_color};
            font-size: {Typography.SIZE_CAPTION}px;
            font-weight: 700;
            background: {bg_color};
            border-radius: {Radius.SM}px;
        """)
        header.addWidget(status_badge)
        layout.addLayout(header)

        # Reasoning
        reason_label = QLabel(reasoning)
        reason_label.setWordWrap(True)
        reason_label.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SIZE_BODY}px;
        """)
        layout.addWidget(reason_label)

        # Safety Flags
        if safety_flags:
            flags_text = "⚠️ " + " | ".join(safety_flags)
            flags_label = QLabel(flags_text)
            flags_label.setWordWrap(True)
            flags_label.setStyleSheet(f"""
                color: {Colors.WARNING};
                font-size: {Typography.SIZE_BODY}px;
                background: {Colors.WARNING_MUTED};
                padding: {Spacing.SM}px;
                border-radius: {Radius.SM}px;
            """)
            layout.addWidget(flags_label)

        # Changes
        if changes:
            changes_text = " \n".join(f"{k} = {v}" for k, v in changes.items())
            changes_label = QLabel(changes_text)
            changes_label.setStyleSheet(f"""
                color: {Colors.TEXT_PRIMARY};
                font-size: {Typography.SIZE_CAPTION}px;
                font-family: {Typography.FAMILY_MONO};
                background: {Colors.BG_APP};
                padding: {Spacing.SM}px;
                border-radius: {Radius.SM}px;
            """)
            layout.addWidget(changes_label)


class TuningPage(WizardPage):
    STEP_TITLE = "Tuning Advisor"
    STEP_SUBTITLE = "Intelligent PID & Filter tuning"

    def __init__(self, state: AppState, job_runner, parent=None):
        self._jobs = job_runner
        super().__init__(state, parent)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        layout.addWidget(self._make_title("Tuning Advisor"))
        layout.addWidget(self._make_subtitle(
            "Our Necro_engine analyzed your flight and generated these tuning suggestions."
        ))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(Spacing.MD)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.addStretch()

        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll, 1)

    def on_enter(self):
        if self.state.has_log and self.state.has_cli:
            self._generate_recommendations()
        else:
            self._show_empty("Missing log or CLI data to generate tuning.")

    def can_proceed(self) -> bool:
        return True

    def _show_empty(self, msg):
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        label = QLabel(msg)
        label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        self.cards_layout.insertWidget(0, label)

    def _generate_recommendations(self):
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        from fpv_tuner.core.pid_tuning.advisor import PIDTuningAdvisor
        from fpv_tuner.core.cli import get_schema
        
        schema = get_schema(self.state.cli.version)
        advisor = PIDTuningAdvisor(schema=schema)

        df = self.state.log.dataframe
        pids = self.state.log.pids  # or self.state.cli.settings? Actually headers and CLI settings
        headers = self.state.log.headers
        
        # Merge CLI settings into headers so advisor has full context
        context_headers = headers.copy()
        if self.state.has_cli:
            for k, v in self.state.cli.settings.items():
                context_headers[k] = v

        gyro_model = self.state.cli.hardware.get("gyro") if self.state.has_cli else None

        recommendation = advisor.analyze(df, pids, context_headers, gyro_model=gyro_model)
        
        # Save to state so ExportPage can use it
        self.state.tuning_recommendation = recommendation

        all_cards = []
        if not recommendation.sub_recommendations:
            self._show_empty("No tuning changes suggested. Your tune looks solid!")
            return

        for sub in recommendation.sub_recommendations:
            card = RecommendationCard(
                kind=sub.kind,
                reasoning=sub.reasoning,
                changes=sub.changes,
                rule_status=sub.rule_status,
                safety_flags=sub.safety_flags,
            )
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
            all_cards.append(card)

        reveal_cards(all_cards, stagger_ms=60)
