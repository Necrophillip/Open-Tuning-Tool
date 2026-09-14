"""
Tuning context and safety-flag vocabulary.

``TuningContext`` is produced by ``version_gyro_guard`` and handed to every
analyser so that no analyser ever makes a version/gyro/slider decision on
its own.

Safety flags are the only way a recommendation can communicate a *risk* to
the UI.  They are strings so new ones can be added without changing types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from fpv_tuner.core.cli.schema import CliSchema


# ── Safety flag vocabulary ────────────────────────────────────────
# Blocking (no automatic CLI until the user confirms):
FLAG_VERSION_MISMATCH = "version_mismatch"
FLAG_GYRO_UNKNOWN_CONSERVATIVE = "gyro_unknown_conservative_mode"
FLAG_CHIRP_UNSUPPORTED = "chirp_unsupported"
FLAG_REDUCES_FILTERING_BLOCKED = "reduces_filtering_blocked"
FLAG_SLIDERS_ACTIVE_CONFLICT = "sliders_active_conflict"
# Informative (non-blocking):
FLAG_REDUCES_FILTERING_RPM_COMPENSATED = "reduces_filtering_rpm_compensated"

BLOCKING_FLAGS = frozenset({
    FLAG_VERSION_MISMATCH,
    FLAG_GYRO_UNKNOWN_CONSERVATIVE,
    FLAG_CHIRP_UNSUPPORTED,
    FLAG_REDUCES_FILTERING_BLOCKED,
    FLAG_SLIDERS_ACTIVE_CONFLICT,
})

RuleStatus = Literal["heuristic_unvalidated", "heuristic_validated", "verified_official"]


@dataclass
class TuningContext:
    """Immutable-ish context describing the log's firmware/hardware state."""
    firmware_version: str = ""
    board: str = ""                     # e.g. "SPEEDYBEEF405AIO"
    manufacturer_id: str = ""           # e.g. "SPBE"
    device_uid: str = ""                # unique FC id from the log
    gyro_model: Optional[str] = None    # None when no live `status` was available
    gyro_model_unknown: bool = False
    version_supported: bool = True
    uses_simplified_sliders: bool = False
    tpa_model: Literal["classic", "curve"] = "classic"
    chirp_detected: bool = False
    schema: Optional[CliSchema] = None
    warnings: list = field(default_factory=list)

    @property
    def blocking_flags(self) -> list[str]:
        """Flags that require explicit user confirmation before applying."""
        return [w for w in self.warnings if w in BLOCKING_FLAGS]

    @property
    def can_auto_apply(self) -> bool:
        """True when no blocking safety flags are present."""
        return not self.blocking_flags
