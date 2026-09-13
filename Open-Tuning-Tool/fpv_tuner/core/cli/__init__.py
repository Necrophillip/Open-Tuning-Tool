"""
Betaflight CLI schema catalog and validation helpers.

This package provides a data-driven, versioned catalog of valid CLI
variables (generated from the firmware source) plus validation so that
tuning suggestions always emit real, in-range ``set`` commands.
"""
from fpv_tuner.core.cli.schema import CliSchema, CliVariable, CliValueError, load_schema, load_schema_from_dict
from fpv_tuner.core.cli.catalog import get_schema, schema_for_version, list_available_schemas
from fpv_tuner.core.cli.validator import (
    normalize_name,
    validate_value,
    validate_change,
    clamp_value,
    LEGACY_ALIASES,
)

__all__ = [
    "CliSchema",
    "CliVariable",
    "CliValueError",
    "load_schema",
    "load_schema_from_dict",
    "get_schema",
    "schema_for_version",
    "list_available_schemas",
    "normalize_name",
    "validate_value",
    "validate_change",
    "clamp_value",
    "LEGACY_ALIASES",
]
