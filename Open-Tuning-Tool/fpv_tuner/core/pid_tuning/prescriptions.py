"""
Prescription builder — turns sub-recommendations into a final, validated
``PIDTuningRecommendation`` with safety flags surfaced and CLI commands
generated (grouped by profile scope).
"""
from __future__ import annotations

from typing import Optional

from fpv_tuner.core.cli.schema import CliSchema
from fpv_tuner.core.cli.validator import clamp_value, normalize_name
from fpv_tuner.core.pid_tuning.models import PIDTuningRecommendation
from fpv_tuner.core.pid_tuning.tuning_context import TuningContext, FLAG_SLIDERS_ACTIVE_CONFLICT


def build_prescription(
    sub_recommendations: list,
    context: TuningContext,
    schema: Optional[CliSchema] = None,
) -> PIDTuningRecommendation:
    rec = PIDTuningRecommendation(context=context, sub_recommendations=sub_recommendations)

    # ── Merge safety flags (sub-recs + context) ────────────────────
    flags: list[str] = []
    for s in sub_recommendations:
        for f in s.safety_flags:
            if f not in flags:
                flags.append(f)
    for w in context.warnings:
        if w not in flags:
            flags.append(w)

    # ── Simplified sliders conflict ───────────────────────────────
    if context.uses_simplified_sliders:
        flags.append(FLAG_SLIDERS_ACTIVE_CONFLICT)
        rec.warnings.append(
            "Tu perfil usa Simplified Tuning Sliders. Estos valores CLI crudos "
            "pueden ser sobrescritos por los sliders o comportarse distinto a lo "
            "esperado. Desactiva los sliders primero o aplica el cambio equivalente "
            "en el slider correspondiente."
        )

    rec.safety_flags = flags

    # ── Collect + clamp changes ───────────────────────────────────
    changes: dict = {}
    for s in sub_recommendations:
        for param, value in s.changes.items():
            changes[param] = _clamp_change(schema, param, value)

    rec.cli_commands = _format_cli(changes, schema)
    return rec


def _clamp_change(schema, param, value):
    if schema is None or param not in schema:
        return value
    var = schema.get(param)
    return clamp_value(var, str(value))


def _scope(schema, param) -> str:
    if schema is not None:
        var = schema.get(param)
        if var is not None:
            return var.scope
    return "master"


def _format_cli(changes: dict, schema) -> str:
    if not changes:
        return "# No changes recommended\n"

    lines = ["# FPV Tuner — PID tuning suggestions", ""]
    buckets = {"master": [], "profile": [], "rateprofile": [], "hardware": []}
    for param, value in changes.items():
        scope = _scope(schema, param)
        buckets.setdefault(scope, []).append((param, value))

    for scope in ("master", "profile", "rateprofile", "hardware"):
        entries = buckets.get(scope)
        if not entries:
            continue
        if scope == "profile":
            lines.append("profile 0")
        elif scope == "rateprofile":
            lines.append("rateprofile 0")
        for param, value in sorted(entries):
            lines.append(f"set {param} = {value}")
        lines.append("")

    lines.append("save")
    return "\n".join(lines)
