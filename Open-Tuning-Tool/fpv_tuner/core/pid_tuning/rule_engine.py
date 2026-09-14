"""
Rule engine — loads the declarative tuning rules from ``tuning_rules.yaml``.

Rules are data (thresholds, multipliers, per-rule ``status``), never code, so
thresholds can be iterated without recompiling.  Each rule's ``status`` is
``heuristic_unvalidated`` until A/B evidence promotes it.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_RULES_PATH = Path(__file__).parent / "tuning_rules.yaml"

DEFAULT_RULES = {
    "rules": {
        "step_response": {
            "overshoot_high": 20.0,
            "overshoot_mid": 12.0,
            "rise_time_slow": 0.20,
            "pid_max": 250,
            "status": "heuristic_unvalidated",
        },
        "dterm_filter": {
            "rms_high": 60.0,
            "lpf_max": 1000,
            "reduction_factor": 0.7,
            "status": "heuristic_unvalidated",
        },
        "gyro_filter": {
            "status": "verified_official",
        },
    }
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_rules(path=None) -> dict:
    """Load tuning rules from YAML (merged over built-in defaults)."""
    try:
        data = yaml.safe_load((Path(path) if path else _RULES_PATH).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        data = {}
    return _deep_merge(DEFAULT_RULES, data or {})


def rget(rules: dict, family: str, key: str, default=None):
    """Get a rule value with a default, from a rules dict like load_rules() output."""
    if rules is None:
        rules = load_rules()
    return rules.get("rules", {}).get(family, {}).get(key, default)


def rstatus(rules: dict, family: str, default: str = "heuristic_unvalidated") -> str:
    return rget(rules, family, "status", default)
