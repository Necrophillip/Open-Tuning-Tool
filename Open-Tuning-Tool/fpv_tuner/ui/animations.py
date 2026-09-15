"""
Animation helpers for the wizard UI.

Provides reusable fade and reveal animations
using QPropertyAnimation.  All durations come from Timing tokens.
"""
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
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


def reveal_cards(cards: list, stagger_ms: int = 80,
                 duration: int = Timing.NORMAL):
    """Reveal a list of card widgets with a stagger effect.

    NOTE: Skips fade_in for cards containing QScrollArea (opacity effects
    conflict with scroll area painting on macOS). Just staggers visibility.
    """
    from PyQt6.QtWidgets import QScrollArea
    from PyQt6.QtCore import QTimer

    for card in cards:
        card.setVisible(False)

    def _show(idx):
        if idx < len(cards):
            cards[idx].setVisible(True)
            if len(cards[idx].findChildren(QScrollArea)) == 0:
                fade_in(cards[idx], duration)
            QTimer.singleShot(stagger_ms, lambda: _show(idx + 1))

    _show(0)
