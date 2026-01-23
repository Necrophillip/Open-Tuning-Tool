# 🛠️ Open-Tuning-Tool Development Tools

This directory contains utility scripts and tools for Open-Tuning-Tool development and setup.

## 📁 Directory Structure

```
tools/
├── blackbox_setup/          # Automated Blackbox-Tools installation
│   ├── install_blackbox.py   # Python installation script (recommended)
│   ├── install_blackbox.sh   # Bash installation script
│   └── README.md             # Detailed installation documentation
```

## 🚀 Quick Start

### Automated Blackbox Installation

The easiest way to set up `blackbox_decode` (required for binary log support):

#### Python Method (Recommended)
```bash
python3 tools/blackbox_setup/install_blackbox.py
```

#### Bash Method
```bash
bash tools/blackbox_setup/install_blackbox.sh
```

For detailed information, see [blackbox_setup/README.md](blackbox_setup/README.md)

## 📋 What Each Tool Does

### Blackbox Setup

**Location**: `tools/blackbox_setup/`

Automates the installation of `blackbox_decode` - the decoder for binary Betaflight logs:

- ✅ Clones official Betaflight repository
- ✅ Auto-detects OS (macOS, Linux, Windows)
- ✅ Compiles from source
- ✅ Installs to system PATH
- ✅ Verifies installation
- ✅ Cleans up unnecessary files

**Requirements**: git, make, C compiler

**Installation Time**: 5-10 minutes (depending on internet speed)

**Supported Platforms**:
- 🍎 macOS 10.14+
- 🐧 Linux (Ubuntu 18.04+, Fedora, etc.)
- 🪟 Windows 10+ (with MinGW/MSVC)

## 🔧 Tool Features

### Logging & Output

All scripts provide:
- 🎨 Color-coded output (success, info, warning, error)
- ⏱️ Progress indicators
- 📊 Detailed error messages
- 🔍 Automatic issue detection

### Error Handling

Scripts handle:
- ✅ Missing dependencies
- ✅ Compilation failures
- ✅ Permission issues
- ✅ Network problems
- ✅ System incompatibilities

### Cross-Platform Support

- macOS: Native support (arm64, x86_64)
- Linux: Full support (tested on Ubuntu, Fedora, Debian)
- Windows: MinGW/MSVC support

## 📚 Additional Resources

- [Betaflight Blackbox Documentation](https://github.com/betaflight/blackbox-log-viewer)
- [Blackbox Log Format](https://github.com/betaflight/blackbox-log-viewer/wiki/Binary-format)
- [Flight Controller Firmware](https://github.com/betaflight/betaflight)

## 🐛 Troubleshooting

### Scripts won't run

**macOS/Linux**:
```bash
# Make scripts executable
chmod +x tools/blackbox_setup/install_blackbox.sh
chmod +x tools/blackbox_setup/install_blackbox.py

# Run again
bash tools/blackbox_setup/install_blackbox.sh
```

**Windows**: Use PowerShell or Git Bash

### Installation fails

See [blackbox_setup/README.md](blackbox_setup/README.md) troubleshooting section

### Permission denied

```bash
# Try with elevated privileges
sudo python3 tools/blackbox_setup/install_blackbox.py

# Or install to user directory (no sudo)
# Script will auto-select ~/.local/bin if system paths unavailable
```

## 🤝 Contributing

Want to improve the tools? 

1. Fork the repository
2. Create a feature branch
3. Make your improvements
4. Test on multiple platforms
5. Submit a pull request

### Code Standards

- Follow PEP 8 (Python)
- Use shellcheck for bash scripts
- Add comments for complex logic
- Test on macOS, Linux, and Windows

## 📝 License

All tools are licensed under MIT License. See the main LICENSE file.

## 📞 Support

Issues or questions?

- 🐛 [Report bugs](https://github.com/Necrophillip/Open-Tuning-Tool/issues)
- 💬 [Discuss features](https://github.com/Necrophillip/Open-Tuning-Tool/discussions)
- 📧 Check [Betaflight community](https://github.com/betaflight/betaflight/discussions)

---

**Happy tuning!** 🚁
