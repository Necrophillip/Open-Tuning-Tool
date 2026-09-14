"""
Data models for the tuning module's recommendations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from fpv_tuner.core.pid_tuning.tuning_context import TuningContext, RuleStatus


@dataclass
class SubRecommendation:
    """One atomic recommendation (PID gains, one filter group, etc.)."""
    kind: Literal["pid", "dterm_filter", "gyro_filter", "rpm_filter", "tpa", "ezlanding"]
    changes: dict                        # {param: value}
    reasoning: str = ""
    rule_status: RuleStatus = "heuristic_unvalidated"
    confidence: float = 0.5              # 0-1
    safety_flags: list = field(default_factory=list)


@dataclass
class PIDTuningRecommendation:
    """Complete tuning recommendation produced by the advisor."""
    context: Optional[TuningContext] = None
    sub_recommendations: list = field(default_factory=list)
    cli_commands: str = ""
    warnings: list = field(default_factory=list)
    safety_flags: list = field(default_factory=list)
    source: Literal["passive_step_response"] = "passive_step_response"

    @property
    def has_changes(self) -> bool:
        return any(bool(s.changes) for s in self.sub_recommendations)
