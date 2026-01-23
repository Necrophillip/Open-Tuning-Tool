# 🚁 Open-Tuning-Tool - FPV Blackbox Analyzer

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/downloads/)
[![Platform: macOS | Linux | Windows](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)](https://en.wikipedia.org/wiki/Cross-platform)
[![Code style: PEP 8](https://img.shields.io/badge/Code%20style-PEP%208-green)](https://www.python.org/dev/peps/pep-0008/)

**Professional FPV Drone PID Tuning Analysis Suite**

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

---

## 📋 Overview

**Open-Tuning-Tool** is a comprehensive desktop application designed for FPV (First-Person View) drone enthusiasts, engineers, and pilots who need to analyze and optimize their quadcopter's flight characteristics. By leveraging Betaflight Blackbox logs, this tool provides deep insights into gyroscope response, noise characteristics, and step response metrics to fine-tune PID gains for optimal flight performance.

Built with modern Python technologies and optimized for high-performance data visualization, Open-Tuning-Tool transforms raw telemetry data into actionable tuning insights.

---

## ✨ Features

### 🔍 Core Analysis Capabilities

- **📊 Step Response Analysis**
  - Automatic detection of step responses in RC commands
  - Real-time normalized visualization with reference lines
  - Precise calculation of rise time, overshoot, and settling time
  - Support for Roll, Pitch, and Yaw axis analysis
  - Second-order system modeling with curve fitting

- **📈 Noise Analysis**
  - Time-domain gyro noise visualization
  - Power Spectral Density (PSD) analysis
  - D-term noise evaluation
  - Interactive filtering threshold adjustment
  - Multi-axis comparison

- **🔄 Trace Viewer**
  - Real-time raw data inspection
  - Synchronized RC command and gyro traces
  - Zoom, pan, and measure capabilities
  - High-performance rendering for large datasets

- **📁 Universal Log Support**
  - Binary Betaflight logs (`.BBL`, `.BFL`)
  - Decoded CSV format
  - On-the-fly decoding integration with `blackbox_decode`
  - Automatic format detection

### 🎯 Advanced Features

- **🔀 Multi-Log Comparison**
  - Load and compare multiple flight logs simultaneously
  - Before/after tuning analysis
  - Visual A/B testing interface
  - Export capabilities for documentation

- **⚡ High Performance**
  - Optimized for large log files (> 100 MB)
  - Real-time rendering with `pyqtgraph`
  - Non-blocking UI with async file loading
  - Memory-efficient data streaming

- **💾 Export Options**
  - PNG/PDF snapshots of analysis
  - CSV data export
  - Metrics summary reports
  - GPX track export (GPS data)

---

## 🛠️ Requirements

### System Requirements
- **OS**: macOS 10.14+, Linux (Ubuntu 18.04+), or Windows 10+
- **Python**: 3.8 or higher
- **RAM**: Minimum 4 GB (8 GB recommended)
- **Disk**: 500 MB free space

### Dependencies
- `PyQt6` - Modern GUI framework
- `pyqtgraph` - High-performance plotting
- `pandas` - Data manipulation and analysis
- `numpy` - Numerical computing
- `scipy` - Scientific computing

### External Tools
- **blackbox-tools**: Required for binary log decoding
  - Download from: [Betaflight Blackbox Log Viewer Releases](https://github.com/betaflight/blackbox-log-viewer/releases)
  - Add `blackbox_decode` executable to your system PATH

---

## 📦 Installation

### Option 1: Using Virtual Environment (Recommended)

```bash
# Clone the repository
git clone https://github.com/Necrophillip/Open-Tuning-Tool.git
cd Open-Tuning-Tool

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r Open-Tuning-Tool/requirements.txt
```

### Option 2: System-wide Installation

```bash
git clone https://github.com/Necrophillip/Open-Tuning-Tool.git
cd Open-Tuning-Tool
pip install -r Open-Tuning-Tool/requirements.txt
```

### Post-Installation: Setup blackbox_decode

1. Download the appropriate `blackbox_decode` binary for your OS from [blackbox-tools releases](https://github.com/betaflight/blackbox-log-viewer/releases)
2. Place it in a directory in your system PATH (e.g., `/usr/local/bin` on macOS/Linux)
3. Verify installation:
   ```bash
   blackbox_decode --version
   ```

---

## 🚀 Usage

### Launch the Application

```bash
# Navigate to Open-Tuning-Tool directory
cd Open-Tuning-Tool

# Run the application
python3 -m fpv_tuner.main
```

### Workflow

1. **Load Logs**
   - Click "Open Logs" to select one or multiple Betaflight log files
   - Logs are automatically decoded and indexed
   - Status bar shows loading progress

2. **Navigate Tabs**
   - **Trace Viewer**: Inspect raw gyro and RC data
   - **Noise Analysis**: Analyze frequency response and noise floor
   - **Step Response**: Study transient response characteristics

3. **Analyze Step Response**
   - Select an axis (Roll/Pitch/Yaw)
   - Tool automatically detects the step response
   - Review metrics: rise time, overshoot, settling time
   - Fitted model shows theoretical response

4. **Export Results**
   - Use "Export" buttons to save charts
   - Generate reports for documentation
   - Share findings with your tuning team

---

## 📊 Analysis Metrics

### Step Response Metrics
| Metric | Description | Target |
|--------|-------------|--------|
| **Rise Time** | Time for response to go from 10% to 90% | 50-100 ms |
| **Overshoot** | Peak value exceeding steady state | 10-20% |
| **Settling Time** | Time to settle within 2% of final value | 200-400 ms |
| **Delay** | Time from input to first response | < 10 ms |

### Noise Metrics
| Metric | Description |
|--------|-------------|
| **RMS Noise** | Root mean square noise level |
| **Peak Noise** | Maximum noise amplitude |
| **Frequency** | Dominant noise frequencies |
| **SNR** | Signal-to-noise ratio |

---

## 📚 Documentation

### File Structure

```
Open-Tuning-Tool/
├── fpv_tuner/
│   ├── analysis/           # Data analysis modules
│   │   ├── step_response.py
│   │   ├── noise.py
│   │   └── system_identification.py
│   ├── gui/                # GUI components
│   │   ├── Main_Window.py
│   │   ├── step_response_tab.py
│   │   ├── noise_tab.py
│   │   └── trace_tab.py
│   ├── blackbox/           # Log file handling
│   │   └── loader.py
│   └── main.py             # Application entry point
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

### Configuration

The application uses automatic detection for most settings:
- Loop frequency estimation from timestamp analysis
- Log format auto-detection
- Optimal resampling rates based on data

Manual configuration options are available in the UI:
- Noise threshold adjustment
- Analysis window size
- Export format selection

---

## 🔧 Troubleshooting

### Application won't start

**Error**: `ModuleNotFoundError: No module named 'PyQt6'`

**Solution**: Install dependencies
```bash
pip install -r Open-Tuning-Tool/requirements.txt
```

### Cannot open binary logs

**Error**: `blackbox_decode not found in PATH`

**Solution**: 
1. Download `blackbox_decode` from [blackbox-tools](https://github.com/betaflight/blackbox-log-viewer/releases)
2. Add to PATH:
   ```bash
   # macOS/Linux
   export PATH="/path/to/blackbox_decode:$PATH"
   
   # Windows: Add to System Environment Variables
   ```

### Slow performance with large files

**Optimization tips**:
- Use decoded CSV logs instead of binary files
- Close other applications
- Increase virtual memory
- Consider log file decimation before analysis

---

## 🤝 Contributing

We welcome contributions! Here's how to get involved:

### Development Setup

```bash
git clone https://github.com/Necrophillip/Open-Tuning-Tool.git
cd Open-Tuning-Tool
git checkout -b feature/your-feature-name

# Install dependencies
pip install -r Open-Tuning-Tool/requirements.txt
```

### Code Style

- Follow PEP 8 guidelines
- Use type hints where applicable
- Add docstrings to all functions
- Keep functions focused and modular

### Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with clear commit messages
3. Test your changes thoroughly
4. Submit a PR with description of changes
5. Address review feedback

---

## 📝 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Betaflight Project** - Flight controller firmware and Blackbox logging
- **PyQt Community** - Modern GUI framework
- **pyqtgraph** - High-performance scientific graphics
- **FPV Community** - For continuous feedback and testing

---

## 📞 Support & Community

- 🐛 **Report Bugs**: [GitHub Issues](https://github.com/Necrophillip/Open-Tuning-Tool/issues)
- 💡 **Feature Requests**: [GitHub Discussions](https://github.com/Necrophillip/Open-Tuning-Tool/discussions)
- 🎮 **FPV Community**: [Betaflight Discussions](https://github.com/betaflight/betaflight/discussions)

---

## 📊 Project Status

```
✅ Core Features: Stable
⚙️  Active Development
🔄 Continuous Improvement
```

**Latest Version**: 1.0.0  
**Last Updated**: January 2026  
**Maintainer**: [@Necrophillip](https://github.com/Necrophillip)

---

<div align="center">

Made with ❤️ for the FPV Community

[⬆ back to top](#-open-tuning-tool---fpv-blackbox-analyzer)

</div>
