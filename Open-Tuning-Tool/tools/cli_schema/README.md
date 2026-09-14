# CLI Schema Generator

Generates versioned Betaflight CLI schemas (JSON) consumed by
`fpv_tuner.core.cli`.

The authoritative source of truth is the firmware `src/main/cli/settings.c`
plus `src/main/fc/parameter_names.h` (which resolves the `PARAM_NAME_*`
macros to their string names).

## Usage

```bash
# Betaflight 4.5
python3 tools/cli_schema/generate_schema.py \
    --ref 4.5-maintenance --version 4.5.0 \
    --out fpv_tuner/core/cli/definitions/betaflight_4_5.json

# Latest (4.6+ / forward-looking)
python3 tools/cli_schema/generate_schema.py \
    --ref master --version 4.6.0 \
    --out fpv_tuner/core/cli/definitions/betaflight_latest.json
```

You can skip the download by passing local copies with `--settings` and
`--names`.

## Adding a new firmware version

1. Generate a new JSON into `fpv_tuner/core/cli/definitions/`.
2. Register it in `fpv_tuner/core/cli/catalog.py` (`_REGISTRY` and
   `_VERSION_ROUTING`).

## Constants

The `CONSTANTS` map in `generate_schema.py` resolves the C macros used in
min/max ranges (e.g. `LPF_MAX_HZ`, `PID_GAIN_MAX`). Unknown constants are
left as `null` so the schema never lies about a range it could not resolve.
