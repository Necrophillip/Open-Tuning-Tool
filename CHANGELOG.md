# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-rc1] - 2026-01-23

### Added
- ✨ **Step Response Analysis Tab** with advanced normalization
  - Automatic detection of step responses in RC commands
  - Unit-step normalized visualization with reference line at Y=1.0
  - Precise calculation of rise time, overshoot, and settling time
  - Support for Roll, Pitch, and Yaw axis analysis
  - Second-order system modeling with curve fitting
  - Peak value display and overshoot percentage

- 📊 **Noise Analysis Tab**
  - Time-domain gyro noise visualization
  - Power Spectral Density (PSD) analysis
  - D-term noise evaluation
  - Interactive filtering threshold adjustment
  - Multi-axis comparison

- 🔄 **Trace Viewer Tab**
  - Real-time raw data inspection
  - Synchronized RC command and gyro traces
  - Zoom, pan, and measure capabilities
  - High-performance rendering for large datasets

- 🛠️ **Automated Blackbox-Tools Installation**
  - One-command installation of blackbox_decode
  - Cross-platform support (macOS, Linux, Windows)
  - Automatic OS detection and compilation
  - Zero-configuration setup process
  - Python and Bash installation scripts

- 📁 **Universal Log Support**
  - Binary Betaflight logs (`.BBL`, `.BFL`)
  - Decoded CSV format
  - On-the-fly decoding integration with `blackbox_decode`
  - Automatic format detection
  - Multi-log simultaneous loading

- 💾 **Export Options**
  - PNG snapshots of analysis
  - CSV data export
  - Metrics summary reports
  - GPX track export (GPS data)

- 🚀 **Build Automation**
  - GitHub Actions CI/CD pipeline
  - Automatic cross-platform compilation (Windows .exe, macOS .dmg, Linux)
  - Automated release asset generation
  - PyInstaller configuration for easy distribution

### Changed
- 🔧 Refactored Step Response Tab for better normalization
  - Both gyro response and fitted model use consistent baseline
  - Improved metric calculations based on normalized data
  - Cleaner visualization with reference lines

### Fixed
- 🐛 Fixed duplicate file structure issue
- 🐛 Fixed import paths for GUI components
- 🐛 Improved error handling in log loading

### Documentation
- 📚 Professional README with comprehensive documentation
- 📚 Detailed installation guides
- 📚 Troubleshooting sections
- 📚 Contributing guidelines
- 📚 API documentation for analysis modules

### Infrastructure
- ✅ GitHub Actions CI/CD setup
- ✅ Cross-platform build configuration
- ✅ Release automation scripts
- ✅ Development tools and utilities

## [Unreleased]

### Added
- 🧪 **CLI Schema Catalog (data-driven, versioned)**
  - Valid, in-range Betaflight CLI variables generated from the firmware `settings.c` (BF 4.5 and 4.6+)
  - Version-aware schema routing (`core/cli/catalog.py`) and validation (`core/cli/validator.py`)
  - Legacy (pre-4.3) name normalization (`gyro_lowpass_hz` → `gyro_lpf1_static_hz`)
  - Generator script in `tools/cli_schema/`

- 🛰 **Serial Transport Layer** (`core/serial/`)
  - Cross-platform port discovery via `pyserial`
  - `SerialConnection` context manager with timeouts and clean error handling
  - MSP framing + client (board version, reboot-to-mass-storage)
  - Betaflight text-CLI session (enter/`set`/`save`)

- 🚁 **Extract Blackbox from Flight Controller**
  - Enter USB mass-storage mode via `MSP_REBOOT`, mount the flash, copy the `.BBL`
  - Available in both the wizard (`Load Log` page) and the advanced view (File menu)

- 📝 **Write Changes to FC**
  - Apply recommended CLI changes directly to a connected FC over the CLI
  - Schema-validated and grouped by profile scope (`profile`/`rateprofile` selectors)

- 🚀 **Automated Extraction + Auto CLI Dump**
  - One-click flow: enter MSC → choose a `.BBL` (if fragmented, excludes the "all" file)
    → eject → reconnect prompt → auto-detect FC → read `dump` over the CLI
  - Removed the manual CLI step from the wizard (settings are now auto-synced)
  - "Sync Settings from FC" action for logs loaded from a file

- 📈 **Review Page (Export)**
  - Step-response plot per axis (roll/pitch/yaw) with overshoot metric
  - Throttle-vs-noise heatmaps with axis selector

- 🗂️ **Per-FC Sessions + Change Control**
  - Sessions keyed by flight controller (`~/.fpv_tuner/sessions/<fc_id>/...`)
  - Full CLI settings + applied changes stored per session
  - "Revert to this session" generates rollback CLI commands

- 🎯 **PID Suggestions**
  - Step-response based P/D gain recommendations per axis (schema-clamped)

### Changed
- 🔧 Prescription engine now emits modern Betaflight 4.5+ names and validates
  every recommendation against the CLI schema (never suggests an invalid command)
- 🔧 `format_cli_commands` groups commands by scope and emits `profile`/`rateprofile`
- 🔧 Wizard flow now has 5 steps (Load Log → Analysis → Diagnosis → Export → Iterate)

### Fixed
- 🐛 MSP direction bytes were swapped (`$M<` to FC vs `$M>` from FC), preventing
  the FC from entering mass-storage mode (verified against a real SPEEDYBEEF405AIO)
- 🐛 Betaflight CLI swallows the first command after entering CLI mode; a warm-up
  blank line is now sent so `set`/`get` are never silently lost (verified on hardware)

### Planned Features
- 🎯 PID Tuning Recommendations
  - AI-based gain optimization
  - Real-time tuning suggestions
  - Before/after comparison analyzer

- 📊 Advanced Filtering
  - Custom filter design UI
  - Filter response visualization
  - Real-time filter preview

- 🎬 Video Integration
  - Flight video synchronization with logs
  - Event markers on video timeline
  - Multi-angle view support

- 📈 Advanced Metrics
  - Frequency response analysis
  - Stability margins calculation
  - Phase margin visualization

---

## Release Notes

### Version 1.0.0-rc1
**Release Date**: January 23, 2026

This is the first Release Candidate of Open-Tuning-Tool, a comprehensive FPV drone PID tuning analysis suite.

**Key Features in RC1**:
- Complete Step Response Analysis with improved normalization
- Comprehensive Noise Analysis tools
- Multi-log comparison capability
- Automated blackbox-tools setup
- Cross-platform support (macOS, Windows, Linux)
- Professional build and distribution system

**Platform Support**:
- 🍎 macOS 10.14+ (Intel & Apple Silicon)
- 🐧 Linux (Ubuntu 18.04+, Fedora, Debian)
- 🪟 Windows 10+ (x64)

**System Requirements**:
- Python 3.8 or higher
- 4 GB RAM minimum (8 GB recommended)
- 500 MB disk space

**Installation**:
See [README.md](README.md) for detailed installation instructions.

**Known Issues**:
- GPX export requires GPS data in blackbox logs
- Very large log files (>500MB) may require more than 8GB RAM
- Dark theme support still in development

**Testing**:
Please report bugs and feature requests on [GitHub Issues](https://github.com/Necrophillip/Open-Tuning-Tool/issues)

---

## Contributors

- [@Necrophillip](https://github.com/Necrophillip) - Lead Developer
- FPV Community - Testing and feedback
- Betaflight Team - Blackbox log format and tools

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
