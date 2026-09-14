"""
PID Tuning Advisor — facade for the intelligent tuning module.

This facade coordinates all analysers with the shared rules, and applies
the safety guards to produce a validated PIDTuningRecommendation.
"""
from __future__ import annotations

from typing import Optional

from fpv_tuner.core.pid_tuning.models import PIDTuningRecommendation
from fpv_tuner.core.pid_tuning.rule_engine import load_rules
from fpv_tuner.core.pid_tuning.version_gyro_guard import build_tuning_context
from fpv_tuner.core.pid_tuning.prescriptions import build_prescription
from fpv_tuner.core.pid_tuning.step_response_pid import analyze as analyze_pid
from fpv_tuner.core.pid_tuning.dterm_analyzer import analyze as analyze_dterm
from fpv_tuner.core.pid_tuning.gyro_filter_analyzer import analyze as analyze_gyro_filter
from fpv_tuner.core.pid_tuning.rpm_filter_analyzer import analyze as analyze_rpm_filter
from fpv_tuner.core.pid_tuning.tpa_ezlanding_analyzer import analyze as analyze_tpa
from fpv_tuner.core.cli.schema import CliSchema
from fpv_tuner.core.cli import get_schema
import pandas as pd


class PIDTuningAdvisor:
    """Facade for the intelligent tuning module."""

    def __init__(self, schema: Optional[CliSchema] = None):
        self.schema = schema or get_schema()

    # ── Public API ────────────────────────────────────────────────

    def analyze(
        self,
        df: pd.DataFrame,
        pids: dict,
        headers: dict,
        gyro_model: Optional[str] = None,
    ) -> PIDTuningRecommendation:
        """
        Run the full tuning analysis pipeline on a log.

        Args:
            df: Log DataFrame (passive flight data).
            pids: PID settings.
            headers: Log-time settings from the blackbox headers.
            gyro_model: Optional gyro model (e.g. from CLI ``status``).

        Returns:
            PIDTuningRecommendation with safety checks applied.
        """
        rules = load_rules()
        context = build_tuning_context(headers, gyro_model=gyro_model, schema=self.schema)

        sub_recommendations = []
        sub_recommendations.extend(analyze_pid(df, pids, headers, context, rules))
        sub_recommendations.extend(analyze_dterm(df, pids, headers, context, rules))
        sub_recommendations.extend(analyze_gyro_filter(df, pids, headers, context, rules))
        sub_recommendations.extend(analyze_rpm_filter(df, pids, headers, context, rules))
        sub_recommendations.extend(analyze_tpa(df, pids, headers, context, rules))

        return build_prescription(sub_recommendations, context, self.schema)


def guess_optimal_pid(df: pd.DataFrame, pids: dict, headers: dict, gyro_model: Optional[str] = None) -> PIDTuningRecommendation:
    """Convenience wrapper for a one-off tuning analysis without a persistent advisor."""
    advisor = PIDTuningAdvisor(schema=get_schema())
    return advisor.analyze(df, pids, headers, gyro_model=gyro_model)
