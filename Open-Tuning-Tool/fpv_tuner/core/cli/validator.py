"""
CLI schema validator — validate suggested ``set`` changes against a schema.

Ensures that every suggested change uses a real variable name for the
target firmware, that the value is within range, and that enum values are
valid.  Also normalizes legacy (pre-4.3) names to their modern equivalents.
"""
from __future__ import annotations

from typing import Optional

from fpv_tuner.core.cli.schema import CliSchema, CliVariable, CliValueError

# Legacy (pre-4.3) filter/parameter names -> modern Betaflight 4.5+ names.
LEGACY_ALIASES = {
    "gyro_lowpass_hz": "gyro_lpf1_static_hz",
    "gyro_lowpass2_hz": "gyro_lpf2_static_hz",
    "gyro_lowpass_type": "gyro_lpf1_type",
    "gyro_lowpass2_type": "gyro_lpf2_type",
    "gyro_lowpass_dyn_min_hz": "gyro_lpf1_dyn_min_hz",
    "gyro_lowpass_dyn_max_hz": "gyro_lpf1_dyn_max_hz",
    "dterm_lowpass_hz": "dterm_lpf1_static_hz",
    "dterm_lowpass2_hz": "dterm_lpf2_static_hz",
    "dterm_lowpass_type": "dterm_lpf1_type",
}


def normalize_name(schema: CliSchema, name: str) -> str:
    """
    Return the canonical name for a setting in ``schema``.

    Handles case and legacy aliases.  Raises CliValueError if the name is
    unknown in the schema.
    """
    key = name.strip().lower()
    if key in schema:
        return key
    aliased = LEGACY_ALIASES.get(key)
    if aliased and aliased in schema:
        return aliased
    raise CliValueError(f"Unknown CLI setting '{name}' for firmware {schema.version or 'unknown'}")


def validate_value(var: CliVariable, value) -> list[str]:
    """
    Validate a value for a variable, returning a list of human-readable
    problems (empty list == valid).
    """
    problems = []
    text = str(value).strip()

    if var.is_array:
        items = text.split(",")
        for item in items:
            item = item.strip()
            if not item:
                problems.append(f"'{var.name}' expects a comma-separated numeric array, but found an empty element in '{text}'")
                continue
            try:
                num = float(item)
            except (TypeError, ValueError):
                problems.append(f"'{var.name}' expects a numeric array, but '{item}' is not numeric")
                continue

            if var.min is not None and num < var.min:
                problems.append(f"'{var.name}' array item {item} is below minimum {var.min}")
            if var.max is not None and num > var.max:
                problems.append(f"'{var.name}' array item {item} is above maximum {var.max}")
        return problems

    if var.is_enum:
        if text not in var.enum_values:
            problems.append(
                f"'{var.name}' must be one of {', '.join(var.enum_values)}, got '{text}'"
            )
        return problems

    try:
        num = float(text)
    except (TypeError, ValueError):
        problems.append(f"'{var.name}' expects a numeric value, got '{text}'")
        return problems

    if var.min is not None and num < var.min:
        problems.append(f"'{var.name}' value {text} is below minimum {var.min}")
    if var.max is not None and num > var.max:
        problems.append(f"'{var.name}' value {text} is above maximum {var.max}")

    return problems


def validate_change(schema: CliSchema, name: str, value) -> list[str]:
    """
    Validate a single suggested change against a schema.

    Returns a list of problem strings (empty == valid).  Raises
    CliValueError only when the name is unknown.
    """
    canonical = normalize_name(schema, name)
    var = schema.get(canonical)
    return validate_value(var, value)


def clamp_value(var: CliVariable, value) -> str:
    """
    Clamp a numeric value to the variable's min/max range.

    Enum and non-numeric values are returned unchanged.  Returns a string.
    """
    text = str(value).strip()

    if var.is_array:
        items = text.split(",")
        clamped_items = []
        for item in items:
            item = item.strip()
            try:
                num = float(item)
            except (TypeError, ValueError):
                clamped_items.append(item)
                continue

            if var.min is not None and num < var.min:
                num = var.min
            if var.max is not None and num > var.max:
                num = var.max

            if var.datatype.startswith(("uint", "int")):
                clamped_items.append(str(int(num)))
            else:
                clamped_items.append(str(num))
        return ",".join(clamped_items)

    try:
        num = float(text)
    except (TypeError, ValueError):
        return text

    if var.min is not None and num < var.min:
        num = var.min
    if var.max is not None and num > var.max:
        num = var.max

    if var.datatype.startswith(("uint", "int")):
        return str(int(num))
    return str(num)
