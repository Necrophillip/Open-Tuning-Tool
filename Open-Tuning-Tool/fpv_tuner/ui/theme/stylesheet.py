"""
Application-wide QSS built from design tokens.

Import `app_stylesheet()` and apply it once on the QApplication.
Widget-specific overrides live close to each widget, referencing
tokens from `tokens.py`.
"""
from fpv_tuner.ui.theme.tokens import Colors, Spacing, Radius, Typography


def app_stylesheet() -> str:
    """Return the global stylesheet for the application."""
    return f"""
/* ═══════════════════════════════════════════════════════════════
   FPV TUNER — Global Dark Theme
   ═══════════════════════════════════════════════════════════════ */

QMainWindow, QDialog {{
    background-color: {Colors.BG_APP};
}}

QWidget {{
    background-color: transparent;
    color: {Colors.TEXT_PRIMARY};
    font-family: {Typography.FAMILY};
    font-size: {Typography.SIZE_BODY}px;
}}

/* ── Menu bar ─────────────────────────────────────────────────── */
QMenuBar {{
    background-color: {Colors.BG_APP};
    border-bottom: 1px solid {Colors.BORDER_SUBTLE};
    padding: {Spacing.XS}px {Spacing.SM}px;
}}
QMenuBar::item {{
    padding: {Spacing.XS}px {Spacing.MD}px;
    border-radius: {Radius.SM}px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background-color: {Colors.BG_ELEVATED};
}}
QMenu {{
    background-color: {Colors.BG_ELEVATED};
    border: 1px solid {Colors.BORDER_SUBTLE};
    border-radius: {Radius.MD}px;
    padding: {Spacing.SM}px;
}}
QMenu::item {{
    padding: {Spacing.SM}px {Spacing.XL}px {Spacing.SM}px {Spacing.MD}px;
    border-radius: {Radius.SM}px;
}}
QMenu::item:selected {{
    background-color: {Colors.ACCENT_MUTED};
    color: {Colors.ACCENT};
}}
QMenu::separator {{
    height: 1px;
    background: {Colors.BORDER_SUBTLE};
    margin: {Spacing.XS}px {Spacing.SM}px;
}}

/* ── Status bar ───────────────────────────────────────────────── */
QStatusBar {{
    background-color: {Colors.BG_APP};
    border-top: 1px solid {Colors.BORDER_SUBTLE};
    color: {Colors.TEXT_SECONDARY};
    padding: {Spacing.XS}px {Spacing.MD}px;
}}

/* ── Push buttons ─────────────────────────────────────────────── */
QPushButton {{
    background-color: {Colors.BG_ELEVATED};
    border: 1px solid {Colors.BORDER_SUBTLE};
    border-radius: {Radius.MD}px;
    padding: {Spacing.SM}px {Spacing.LG}px;
    color: {Colors.TEXT_PRIMARY};
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {Colors.BG_OVERLAY};
    border-color: {Colors.BORDER_STRONG};
}}
QPushButton:pressed {{
    background-color: {Colors.BG_SURFACE};
}}
QPushButton:disabled {{
    color: {Colors.TEXT_DISABLED};
    background-color: {Colors.BG_SURFACE};
    border-color: {Colors.BORDER_SUBTLE};
}}

QPushButton[variant="primary"] {{
    background-color: {Colors.ACCENT};
    border: none;
    color: {Colors.BG_APP};
}}
QPushButton[variant="primary"]:hover {{
    background-color: {Colors.ACCENT_HOVER};
}}
QPushButton[variant="primary"]:pressed {{
    background-color: {Colors.ACCENT_PRESSED};
}}
QPushButton[variant="primary"]:disabled {{
    background-color: {Colors.ACCENT_MUTED};
    color: {Colors.TEXT_DISABLED};
}}

QPushButton[variant="ghost"] {{
    background-color: transparent;
    border: 1px solid {Colors.BORDER_SUBTLE};
    color: {Colors.TEXT_SECONDARY};
}}
QPushButton[variant="ghost"]:hover {{
    border-color: {Colors.ACCENT};
    color: {Colors.ACCENT};
}}

/* ── Combo boxes ──────────────────────────────────────────────── */
QComboBox {{
    background-color: {Colors.BG_ELEVATED};
    border: 1px solid {Colors.BORDER_SUBTLE};
    border-radius: {Radius.MD}px;
    padding: {Spacing.SM}px {Spacing.MD}px;
    min-height: 20px;
}}
QComboBox:hover {{
    border-color: {Colors.BORDER_STRONG};
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox QAbstractItemView {{
    background-color: {Colors.BG_ELEVATED};
    border: 1px solid {Colors.BORDER_SUBTLE};
    border-radius: {Radius.MD}px;
    selection-background-color: {Colors.ACCENT_MUTED};
    selection-color: {Colors.ACCENT};
    padding: {Spacing.SM}px;
    outline: none;
}}

/* ── Tab widget (legacy advanced views) ───────────────────────── */
QTabWidget::pane {{
    border: 1px solid {Colors.BORDER_SUBTLE};
    border-radius: {Radius.MD}px;
    background-color: {Colors.BG_SURFACE};
    top: -1px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {Colors.TEXT_SECONDARY};
    padding: {Spacing.SM}px {Spacing.LG}px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: {Spacing.SM}px;
}}
QTabBar::tab:selected {{
    color: {Colors.ACCENT};
    border-bottom: 2px solid {Colors.ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {Colors.TEXT_PRIMARY};
}}

/* ── Scroll bars ──────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {Colors.BORDER_SUBTLE};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {Colors.TEXT_DISABLED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {Colors.BORDER_SUBTLE};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Splitters ────────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {Colors.BORDER_SUBTLE};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

/* ── Tooltips ─────────────────────────────────────────────────── */
QToolTip {{
    background-color: {Colors.BG_OVERLAY};
    color: {Colors.TEXT_PRIMARY};
    border: 1px solid {Colors.BORDER_SUBTLE};
    border-radius: {Radius.SM}px;
    padding: {Spacing.SM}px;
}}

/* ── Lists ────────────────────────────────────────────────────── */
QListWidget {{
    background-color: {Colors.BG_SURFACE};
    border: 1px solid {Colors.BORDER_SUBTLE};
    border-radius: {Radius.MD}px;
    padding: {Spacing.SM}px;
    outline: none;
}}
QListWidget::item {{
    padding: {Spacing.SM}px;
    border-radius: {Radius.SM}px;
}}
QListWidget::item:selected {{
    background-color: {Colors.ACCENT_MUTED};
    color: {Colors.ACCENT};
}}
QListWidget::item:hover:!selected {{
    background-color: {Colors.BG_ELEVATED};
}}

/* ── Dock widgets ─────────────────────────────────────────────── */
QDockWidget {{
    color: {Colors.TEXT_SECONDARY};
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
    font-weight: 600;
}}
QDockWidget::title {{
    background-color: {Colors.BG_APP};
    padding: {Spacing.SM}px;
    border-bottom: 1px solid {Colors.BORDER_SUBTLE};
}}

/* ── Toolbar ──────────────────────────────────────────────────── */
QToolBar {{
    background-color: {Colors.BG_APP};
    border-bottom: 1px solid {Colors.BORDER_SUBTLE};
    padding: {Spacing.XS}px;
    spacing: {Spacing.SM}px;
}}
QToolButton {{
    background-color: transparent;
    border-radius: {Radius.SM}px;
    padding: {Spacing.SM}px;
}}
QToolButton:hover {{
    background-color: {Colors.BG_ELEVATED};
}}

/* ── Progress bar ─────────────────────────────────────────────── */
QProgressBar {{
    background-color: {Colors.BG_SURFACE};
    border: none;
    border-radius: {Radius.SM}px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {Colors.ACCENT};
    border-radius: {Radius.SM}px;
}}

/* ── Checkboxes ───────────────────────────────────────────────── */
QCheckBox {{
    spacing: {Spacing.SM}px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: {Radius.SM}px;
    border: 1px solid {Colors.BORDER_SUBTLE};
    background-color: {Colors.BG_ELEVATED};
}}
QCheckBox::indicator:checked {{
    background-color: {Colors.ACCENT};
    border-color: {Colors.ACCENT};
}}
"""
