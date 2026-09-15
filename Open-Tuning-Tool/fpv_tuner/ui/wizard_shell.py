"""
Wizard Shell — the main container that ties everything together.

Layout:
  ┌──────────────────────────────────────────────────┐
  │  Stepper  │         Page Content                 │
  │  (left)   │                                      │
  │           │                                      │
  │           ├──────────────────────────────────────┤
  │           │  [← Back]          [Next →]          │
  └──────────────────────────────────────────────────┘
"""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLabel, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QColor

from fpv_tuner.ui.theme import Colors, Spacing, Radius, Typography, Timing
from fpv_tuner.ui.widgets.step_indicator import StepIndicator
from fpv_tuner.ui.app_state import AppState
from fpv_tuner.ui.jobs import JobRunner
from fpv_tuner.ui.animations import fade_in
from fpv_tuner.ui.toasts import ToastManager


def _has_scroll_area(widget) -> bool:
    """Check if a widget tree contains a QScrollArea (opacity effects break these)."""
    from PyQt6.QtWidgets import QScrollArea
    return len(widget.findChildren(QScrollArea)) > 0


# ── Wizard step definitions ──────────────────────────────────────

WIZARD_STEPS = [
    {"title": "Cargar",      "subtitle": "Blackbox log"},
    {"title": "Análisis",    "subtitle": "Procesamiento matemático"},
    {"title": "Diagnóstico", "subtitle": "Filtros y Ruido"},
    {"title": "Tuning",      "subtitle": "PIDs y Feedforward"},
    {"title": "Exportar",    "subtitle": "Obtén la configuración"},
    {"title": "Iterar",      "subtitle": "Vuela, loguea, repite"},
]


class WizardShell(QWidget):
    """Main wizard container with stepper, pages, and navigation."""

    # Emitted when user wants to switch to the advanced tab view
    advanced_mode_requested = pyqtSignal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.jobs = JobRunner(self)
        self._current_step = 0
        self._max_unlocked = 0
        self._build_ui()
        self.toasts = ToastManager(self)
        self._connect_state()
        self._update_nav()

    # ── UI construction ───────────────────────────────────────────

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Left: stepper panel ──
        stepper_panel = QFrame()
        stepper_panel.setFixedWidth(240)
        stepper_panel.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_SURFACE};
                border-right: 1px solid {Colors.BORDER_SUBTLE};
            }}
        """)
        stepper_layout = QVBoxLayout(stepper_panel)
        stepper_layout.setContentsMargins(0, Spacing.LG, 0, Spacing.LG)

        # Logo / title
        logo = QLabel("🚁 FPV Tuner")
        logo.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            font-size: {Typography.SIZE_TITLE}px;
            font-weight: 700;
            padding: 0 {Spacing.MD}px;
        """)
        stepper_layout.addWidget(logo)
        stepper_layout.addSpacing(Spacing.LG)

        self.stepper = StepIndicator()
        self.stepper.set_steps(WIZARD_STEPS)
        self.stepper.step_clicked.connect(self._on_step_clicked)
        stepper_layout.addWidget(self.stepper, 1)

        # Advanced mode link
        advanced_label = QLabel("🔬 Advanced View")
        advanced_label.setCursor(Qt.CursorShape.PointingHandCursor)
        advanced_label.setStyleSheet(f"""
            color: {Colors.TEXT_DISABLED};
            font-size: {Typography.SIZE_CAPTION}px;
            padding: {Spacing.SM}px {Spacing.MD}px;
        """)
        advanced_label.mousePressEvent = lambda e: self.advanced_mode_requested.emit()
        stepper_layout.addWidget(advanced_label)

        main_layout.addWidget(stepper_panel)

        # ── Right: content + nav ──
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Stacked pages
        self.stack = QStackedWidget()
        self._pages = []

        # Import pages here to avoid circular imports
        from fpv_tuner.ui.pages.log_page import LogPage
        from fpv_tuner.ui.pages.analysis_page import AnalysisPage
        from fpv_tuner.ui.pages.diagnosis_page import DiagnosisPage
        from fpv_tuner.ui.pages.tuning_page import TuningPage
        from fpv_tuner.ui.pages.export_page import ExportPage
        from fpv_tuner.ui.pages.iterate_page import IteratePage

        page_classes = [LogPage, AnalysisPage, DiagnosisPage, TuningPage, ExportPage, IteratePage]

        for PageClass in page_classes:
            if PageClass in (LogPage, AnalysisPage, DiagnosisPage, TuningPage, ExportPage):
                page = PageClass(self.state, self.jobs)
            else:
                page = PageClass(self.state)
            page.validity_changed.connect(self._update_nav)
            self._pages.append(page)
            self.stack.addWidget(page)

        # Connect Iterate page's new session signal
        iterate_page = self._pages[-1]  # IteratePage
        iterate_page.new_session_requested.connect(self.reset_wizard)

        content_layout.addWidget(self.stack, 1)

        # ── Bottom navigation ──
        nav_bar = QFrame()
        nav_bar.setFixedHeight(60)
        nav_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_SURFACE};
                border-top: 1px solid {Colors.BORDER_SUBTLE};
            }}
        """)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(Spacing.LG, 0, Spacing.LG, 0)

        self.back_btn = QPushButton("←  Back")
        self.back_btn.setProperty("variant", "ghost")
        self.back_btn.clicked.connect(self._go_back)
        nav_layout.addWidget(self.back_btn)

        nav_layout.addStretch()

        self.skip_label = QLabel("")
        self.skip_label.setStyleSheet(f"""
            color: {Colors.TEXT_DISABLED};
            font-size: {Typography.SIZE_CAPTION}px;
        """)
        nav_layout.addWidget(self.skip_label)
        nav_layout.addSpacing(Spacing.MD)

        self.next_btn = QPushButton("Next  →")
        self.next_btn.setProperty("variant", "primary")
        self.next_btn.setMinimumWidth(120)
        self.next_btn.clicked.connect(self._go_next)
        nav_layout.addWidget(self.next_btn)

        content_layout.addWidget(nav_bar)
        main_layout.addWidget(content_area, 1)

    # ── State connections ─────────────────────────────────────────

    def _connect_state(self):
        self.state.log_loaded.connect(self._update_nav)
        self.state.log_cleared.connect(self._update_nav)
        self.state.cli_loaded.connect(self._update_nav)
        self.state.analysis_updated.connect(self._update_nav)
        # Toasts (signals carry no payload — read from state)
        self.state.log_loaded.connect(self._toast_log_loaded)
        self.state.log_cleared.connect(lambda: self.toasts.info("Log cleared"))
        self.state.cli_loaded.connect(self._toast_cli_loaded)
        self.state.analysis_updated.connect(self._toast_analysis)

    # ── Toast helpers (read from state, no signal payload) ──────

    def _toast_log_loaded(self):
        if self.state.has_log:
            log = self.state.log
            name = log.file_path.split("/")[-1] if log.file_path else "log"
            self.toasts.success(f"Loaded {name} — {log.n_rows:,} samples")

    def _toast_cli_loaded(self):
        if self.state.has_cli:
            cli = self.state.cli
            msg = f"CLI v{cli.version} loaded" if cli.version else "CLI dump loaded"
            self.toasts.success(msg)

    def _toast_analysis(self):
        if self.state.analysis and self.state.analysis.completed:
            self.toasts.success("Analysis complete")

    # ── Navigation ────────────────────────────────────────────────

    def _go_next(self):
        step = self._current_step + 1
        if self.state.tuning_mode == "FILTERS" and step == 3:
            step = 4
        if self.state.tuning_mode in ("PIDS", "COMPLEMENTARY") and step == 2:
            step = 3
        if step < len(WIZARD_STEPS):
            self._go_to_step(step)

    def _go_back(self):
        step = self._current_step - 1
        if self.state.tuning_mode == "FILTERS" and step == 3:
            step = 2
        if self.state.tuning_mode in ("PIDS", "COMPLEMENTARY") and step == 2:
            step = 1
        if step >= 0:
            self._go_to_step(step)

    def _on_step_clicked(self, index: int):
        # Can only navigate to unlocked steps
        if index <= self._max_unlocked:
            self._go_to_step(index)

    def _go_to_step(self, index: int):
        self._current_step = index
        self._max_unlocked = max(self._max_unlocked, index)

        # Update UI
        self.stack.setCurrentIndex(index)
        self.stepper.set_current(index, self._max_unlocked)
        self.state.set_step(index)

        # Notify the page
        self._pages[index].on_enter()
        self._update_nav()

        # Fade in the new page (skip if it has complex children like scroll areas)
        current_widget = self.stack.currentWidget()
        if current_widget and not _has_scroll_area(current_widget):
            fade_in(current_widget, Timing.NORMAL)

    def _update_nav(self):
        """Update button states based on current page validity."""
        page = self._pages[self._current_step]
        can_next = page.can_proceed()
        is_last = self._current_step == len(WIZARD_STEPS) - 1

        self.next_btn.setEnabled(can_next and not is_last)
        self.back_btn.setEnabled(self._current_step > 0)

        if is_last:
            self.next_btn.setText("Done  ✓")
        else:
            self.next_btn.setText("Next  →")

        self.skip_label.setText("")

    # ── Public API ────────────────────────────────────────────────

    def reset_wizard(self):
        """Reset everything for a new session."""
        self.state.clear_log()
        self.state.clear_cli()
        self._max_unlocked = 0
        self._go_to_step(0)
