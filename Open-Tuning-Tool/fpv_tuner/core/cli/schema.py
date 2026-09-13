"""
CLI schema — typed representation of a Betaflight CLI variable catalog.

Pure Python, no Qt.  Loads a versioned JSON schema (generated from the
firmware ``settings.c`` by ``tools/cli_schema/generate_schema.py``) and
exposes it as dataclasses for validation and code-generation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

SCOPES = ("master", "profile", "rateprofile", "hardware")


class CliValueError(ValueError):
    """Raised when a CLI value or name is invalid for a given schema."""


@dataclass
class CliVariable:
    """One CLI ``set`` variable and its constraints."""
    name: str
    var_type: str = ""
    datatype: str = ""
    scope: str = "master"
    min: Optional[float] = None
    max: Optional[float] = None
    default: Optional[str] = None
    enum_table: Optional[str] = None
    enum_values: Optional[list] = None

    @property
    def is_enum(self) -> bool:
        return bool(self.enum_values)

    @property
    def is_numeric(self) -> bool:
        return self.datatype.startswith(("int", "uint"))


@dataclass
class CliSchema:
    """A full, versioned catalog of CLI variables for one firmware release."""
    firmware: str = "betaflight"
    version: str = ""
    source_ref: str = ""
    variables: dict = field(default_factory=dict)

    def get(self, name: str) -> Optional[CliVariable]:
        return self.variables.get(name.lower())

    def __contains__(self, name: str) -> bool:
        return name.lower() in self.variables

    def __len__(self) -> int:
        return len(self.variables)


def load_schema_from_dict(data: dict) -> CliSchema:
    """Build a CliSchema from a decoded JSON dict."""
    schema = CliSchema(
        firmware=data.get("firmware", "betaflight"),
        version=data.get("version", ""),
        source_ref=data.get("source_ref", ""),
    )
    for raw in data.get("variables", {}).values():
        var = CliVariable(
            name=raw["name"],
            var_type=raw.get("type", ""),
            datatype=raw.get("datatype", ""),
            scope=raw.get("scope", "master"),
            min=raw.get("min"),
            max=raw.get("max"),
            default=raw.get("default"),
            enum_table=raw.get("enum_table"),
            enum_values=raw.get("enum_values"),
        )
        schema.variables[var.name.lower()] = var
    return schema


def load_schema(path: str | Path) -> CliSchema:
    """Load a schema from a JSON file."""
    with open(path, "r", encoding="utf-8") as fh:
        return load_schema_from_dict(json.load(fh))
