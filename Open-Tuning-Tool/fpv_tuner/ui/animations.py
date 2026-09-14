"""
Animation helpers for the wizard UI.

Provides reusable fade, slide, and reveal animations
using QPropertyAnimation.  All durations come from Timing tokens.
"""
from PyQt6.QtCore import (
    QPropertyAnimation, QEasingCurve, QRect, QPoint,
    QParallelAnimationGroup, QSequentialAnimationGroup,
    pyqtProperty, Qt,
)
from PyQt6.QtWidgets import QWidget, QGraphicsOpacityEffect

from fpv_tuner.ui.theme import Timing


def fade_in(widget: QWidget, duration: int = Timing.NORMAL,
            on_finished=None) -> QPropertyAnimation:
    """Fade a widget from transparent to opaque."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    effect.setOpacity(0.0)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    if on_finished:
        anim.finished.connect(on_finished)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def fade_out(widget: QWidget, duration: int = Timing.FAST,
             on_finished=None) -> QPropertyAnimation:
    """Fade a widget to transparent."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(effect.opacity())
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.Type.InCubic)
    if on_finished:
        anim.finished.connect(on_finished)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def slide_in_from_right(widget: QWidget, offset: int = 30,
                        duration: int = Timing.NORMAL,
                        on_finished=None) -> QPropertyAnimation:
    """Slide a widget in from the right + fade in."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
    effect.setOpacity(0.0)

    # Position animation
    geo = widget.geometry()
    start_geo = QRect(geo.x() + offset, geo.y(), geo.width(), geo.height())

    pos_anim = QPropertyAnimation(widget, b"geometry", widget)
    pos_anim.setDuration(duration)
    pos_anim.setStartValue(start_geo)
    pos_anim.setEndValue(geo)
    pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # Opacity animation
    fade_anim = QPropertyAnimation(effect, b"opacity", widget)
    fade_anim.setDuration(duration)
    fade_anim.setStartValue(0.0)
    fade_anim.setEndValue(1.0)
    fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    group = QParallelAnimationGroup(widget)
    group.addAnimation(pos_anim)
    group.addAnimation(fade_anim)
    if on_finished:
        group.finished.connect(on_finished)
    group.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return pos_anim  # Return one anim for chaining


def reveal_cards(cards: list, stagger_ms: int = 80,
                 duration: int = Timing.NORMAL):
    """Reveal a list of card widgets with a stagger effect.

    NOTE: Skips fade_in for cards containing QScrollArea (opacity effects
    conflict with scroll area painting on macOS). Just staggers visibility.
    """
    from PyQt6.QtWidgets import QScrollArea

    for card in cards:
        card.setVisible(False)

    def _show(idx):
        if idx < len(cards):
            cards[idx].setVisible(True)
            # Only fade if no scroll area inside
            if len(cards[idx].findChildren(QScrollArea)) == 0:
                fade_in(cards[idx], duration)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(stagger_ms, lambda: _show(idx + 1))

    _show(0)


def pulse_widget(widget: QWidget, scale: float = 1.02,
                 duration: int = Timing.FAST):
    """Quick scale pulse (for success feedback)."""
    geo = widget.geometry()
    dw = int(geo.width() * (scale - 1))
    dh = int(geo.height() * (scale - 1))
    enlarged = QRect(geo.x() - dw // 2, geo.y() - dh // 2,
                     geo.width() + dw, geo.height() + dh)

    anim = QPropertyAnimation(widget, b"geometry", widget)
    anim.setDuration(duration)
    anim.setStartValue(geo)
    anim.setKeyValueAt(0.5, enlarged)
    anim.setEndValue(geo)
    anim.setEasingCurve(QEasingCurve.Type.OutBack)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim
