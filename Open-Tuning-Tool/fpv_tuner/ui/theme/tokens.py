"""
Design tokens for the FPV Tuner dark theme.

Single source of truth for colors, spacing, typography and timing.
Everything visual in the app should reference these tokens — never
hardcode hex values in widgets.
"""


class Colors:
    """Color palette — dark theme tuned for long tuning sessions."""

    # ── Backgrounds (darkest → lightest) ──────────────────────────
    BG_APP = "#0F172A"          # App window background
    BG_SURFACE = "#192134"      # Cards, panels
    BG_ELEVATED = "#1E293B"     # Raised elements (hover, dropdowns)
    BG_OVERLAY = "#334155"      # Highest elevation (popovers)

    # ── Borders ───────────────────────────────────────────────────
    BORDER_SUBTLE = "#232A38"   # Default hairline borders
    BORDER_STRONG = "#35405266" # Emphasized borders (semi-transparent)

    # ── Text ──────────────────────────────────────────────────────
    TEXT_PRIMARY = "#E6EAF2"    # Main content
    TEXT_SECONDARY = "#9AA4B8"  # Descriptions, captions
    TEXT_DISABLED = "#5A6376"   # Disabled / placeholder

    # ── Accent (brand) ────────────────────────────────────────────
    ACCENT = "#6366F1"          # Primary actions, links, active step
    ACCENT_HOVER = "#818CF8"
    ACCENT_PRESSED = "#4F46E5"
    ACCENT_MUTED = "#312E81"    # Accent-tinted backgrounds

    # ── Semantic ──────────────────────────────────────────────────
    SUCCESS = "#3DDC84"
    SUCCESS_MUTED = "#1B3A2B"
    WARNING = "#FFB020"
    WARNING_MUTED = "#3D3018"
    DANGER = "#FF5C5C"
    DANGER_MUTED = "#3D1E1E"
    INFO = "#8E9BB4"

    # ── Charts ────────────────────────────────────────────────────
    CHART_PRE_FILTER = "#FF5C5C"     # Red  — raw/unfiltered
    CHART_POST_FILTER = "#3DDC84"    # Green — filtered
    CHART_THROTTLE = "#4CC2FF"       # Accent — throttle traces
    CHART_GRID = "#232A38"

    # ── Stepper ───────────────────────────────────────────────────
    STEP_DONE = SUCCESS
    STEP_ACTIVE = ACCENT
    STEP_PENDING = TEXT_DISABLED
    STEP_LOCKED = BORDER_SUBTLE


class Spacing:
    """Consistent spacing scale (px)."""
    XS = 4
    SM = 8
    MD = 16
    LG = 24
    XL = 32
    XXL = 48


class Radius:
    """Corner radius scale (px)."""
    SM = 6
    MD = 10
    LG = 14
    PILL = 999


class Typography:
    """Font stacks and sizes."""
    FAMILY = "'Helvetica Neue', 'Inter', sans-serif"
    FAMILY_MONO = "'Menlo', 'JetBrains Mono', 'SF Mono', monospace"

    SIZE_DISPLAY = 32   # Hero titles
    SIZE_TITLE = 24     # Page titles
    SIZE_HEADING = 18   # Section headings
    SIZE_BODY = 14      # Default body
    SIZE_CAPTION = 12   # Captions, hints


class Timing:
    """Animation durations (ms)."""
    FAST = 150      # Micro-interactions (hover, press)
    NORMAL = 250    # Standard transitions
    SLOW = 400      # Page transitions, reveals
