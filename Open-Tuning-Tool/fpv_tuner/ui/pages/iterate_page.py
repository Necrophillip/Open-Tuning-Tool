"""
Step 6 — Iterate.

Prompts the user to fly with the new settings, then drop the new log
to compare against the previous session.  Shows session history.
"""
from datetime import datetime
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QScrollArea, QWidget, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal

from fpv_tuner.ui.pages.base_page import WizardPage
from fpv_tuner.ui.app_state import AppState
from fpv_tuner.ui.theme import Colors, Spacing, Radius, Typography
from fpv_tuner.core.session_history import list_sessions, load_session, compare_sessions


class IteratePage(WizardPage):
    STEP_TITLE = "Iterate"
    STEP_SUBTITLE = "Fly, log, repeat until perfect"

    new_session_requested = pyqtSignal()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.LG)

        # Hero section (compact)
        hero_row = QHBoxLayout()
        hero_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero = QLabel("🛸")
        hero.setStyleSheet("font-size: 48px;")
        hero_row.addWidget(hero)
        layout.addLayout(hero_row)

        title = QLabel("Go fly with your new settings!")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: {Typography.SIZE_TITLE}px;
            font-weight: 700;
        """)
        layout.addWidget(title)

        subtitle = QLabel(
            "When you land, grab the new blackbox log and start a new session.\n"
            "We'll compare it against your previous sessions below."
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        subtitle.setStyleSheet(f"""
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SIZE_BODY}px;
            line-height: 1.6;
            padding: 0px 20px;
        """)
        layout.addWidget(subtitle)

        # Quick restart button
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.restart_btn = QPushButton("🔄  Start New Session")
        self.restart_btn.setProperty("variant", "primary")
        self.restart_btn.setMinimumHeight(44)
        self.restart_btn.setMinimumWidth(220)
        self.restart_btn.clicked.connect(self._on_restart_clicked)
        btn_row.addWidget(self.restart_btn)
        layout.addLayout(btn_row)

        # Session history header
        history_title = QLabel("📊  Session History")
        history_title.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: {Typography.SIZE_HEADING}px;
            font-weight: 600;
            padding-top: {Spacing.MD}px;
        """)
        layout.addWidget(history_title)

        # Scrollable session list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
        """)
        self.sessions_container = QWidget()
        self.sessions_layout = QVBoxLayout(self.sessions_container)
        self.sessions_layout.setSpacing(Spacing.SM)
        self.sessions_layout.setContentsMargins(0, 0, 0, 0)
        self.sessions_layout.addStretch()
        scroll.setWidget(self.sessions_container)
        layout.addWidget(scroll, 1)

        layout.addStretch()

    def on_enter(self):
        self._refresh_sessions()

    def _on_restart_clicked(self):
        self.new_session_requested.emit()

    def can_proceed(self) -> bool:
        return True

    # ── Session history UI ────────────────────────────────────────

    def _refresh_sessions(self):
        """Reload session list from disk."""
        # Clear old cards (keep stretch)
        while self.sessions_layout.count() > 1:
            item = self.sessions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sessions = list_sessions(limit=20)
        if not sessions:
            empty = QLabel("No sessions yet.\nComplete an analysis to see history here.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"""
                color: {Colors.TEXT_DISABLED};
                font-size: {Typography.SIZE_BODY}px;
                padding: {Spacing.XL}px;
            """)
            self.sessions_layout.insertWidget(0, empty)
            return

        # Show comparison if we have 2+ sessions
        if len(sessions) >= 2:
            comp_card = self._build_comparison_card(sessions[1], sessions[0])
            self.sessions_layout.insertWidget(0, comp_card)

        # Individual session cards
        for snap in sessions[:10]:
            card = self._build_session_card(snap)
            self.sessions_layout.insertWidget(self.sessions_layout.count() - 1, card)

    def _build_session_card(self, snap) -> QFrame:
        """One session summary card."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_SURFACE};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: {Radius.MD}px;
                padding: {Spacing.MD}px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(Spacing.XS)

        # Header: date + file
        header = QHBoxLayout()
        date_str = datetime.fromtimestamp(snap.timestamp).strftime("%b %d, %H:%M")
        date_label = QLabel(f"📅 {date_str}")
        date_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Typography.SIZE_CAPTION}px;")
        header.addWidget(date_label)
        header.addStretch()

        name = snap.log_file.split("/")[-1] if snap.log_file else "unknown"
        file_label = QLabel(f"📁 {name}")
        file_label.setStyleSheet(f"color: {Colors.TEXT_DISABLED}; font-size: {Typography.SIZE_CAPTION}px;")
        header.addWidget(file_label)
        layout.addLayout(header)

        # Metrics row
        metrics = []
        if snap.n_critical:
            metrics.append(f"🔴 {snap.n_critical} critical")
        if snap.n_warning:
            metrics.append(f"🟡 {snap.n_warning} warnings")
        if snap.gyro_rms:
            avg = sum(snap.gyro_rms.values()) / len(snap.gyro_rms)
            metrics.append(f"Gyro RMS: {avg:.1f}")
        if snap.n_changes:
            metrics.append(f"📝 {snap.n_changes} changes")

        metrics_label = QLabel("  •  ".join(metrics) if metrics else "Clean log ✅")
        metrics_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: {Typography.SIZE_BODY}px;
        """)
        layout.addWidget(metrics_label)

        # Revert action (only if this session recorded applied changes)
        if getattr(snap, "applied_changes", None):
            revert_row = QHBoxLayout()
            revert_btn = QPushButton("↩  Revert to this session")
            revert_btn.setProperty("variant", "ghost")
            revert_btn.clicked.connect(lambda _=False, s=snap: self._show_revert(s))
            revert_row.addStretch()
            revert_row.addWidget(revert_btn)
            layout.addLayout(revert_row)

        return card

    def _show_revert(self, snap):
        """Show the CLI commands that revert to a previous session."""
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from fpv_tuner.core.session_history import build_revert_commands
        commands = build_revert_commands(snap)
        box = QMessageBox(self)
        box.setWindowTitle("Revert Commands")
        box.setText(
            "Paste these commands into the Betaflight CLI (or use 'Write to FC' "
            "after selecting the FC) to revert to this session's settings:"
        )
        box.setDetailedText(commands)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _build_comparison_card(self, older, newer) -> QFrame:
        """Compare two most recent sessions."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.ACCENT_MUTED};
                border: 1px solid {Colors.ACCENT};
                border-radius: {Radius.MD}px;
                padding: {Spacing.MD}px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(Spacing.SM)

        title = QLabel("📈  Latest vs Previous")
        title.setStyleSheet(f"""
            color: {Colors.ACCENT};
            font-size: {Typography.SIZE_HEADING}px;
            font-weight: 600;
            border: none;
        """)
        layout.addWidget(title)

        result = compare_sessions(older, newer)

        for text in result.improvements:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {Colors.SUCCESS}; font-size: {Typography.SIZE_BODY}px; border: none;")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)

        for text in result.regressions:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {Colors.DANGER}; font-size: {Typography.SIZE_BODY}px; border: none;")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)

        for text in result.unchanged:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Typography.SIZE_BODY}px; border: none;")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)

        if not result.improvements and not result.regressions:
            lbl = QLabel("No significant changes detected")
            lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Typography.SIZE_BODY}px; border: none;")
            layout.addWidget(lbl)

        return card
