# 🛠️ Blackbox-Tools Setup

Automated installation script for `blackbox_decode` - the binary decoder for Betaflight Blackbox logs.

## 📋 Overview

This directory contains automated installation scripts that will:

1. ✅ Clone the `blackbox-tools` repository
2. ✅ Detect your operating system (macOS, Linux, Windows)
3. ✅ Compile the `blackbox_decode` executable
4. ✅ Move it to your system PATH
5. ✅ Verify the installation
6. ✅ Clean up unnecessary repository files

## 🚀 Quick Start

### Python Method (Recommended)

```bash
# Navigate to Open-Tuning-Tool directory
cd Open-Tuning-Tool

# Run the installation script
python3 tools/blackbox_setup/install_blackbox.py
```

### Bash Method

```bash
# Navigate to Open-Tuning-Tool directory
cd Open-Tuning-Tool

# Run the bash script
bash tools/blackbox_setup/install_blackbox.sh
```

## 📋 Requirements

The installation script requires:

- **git**: For cloning the repository
- **make**: For compilation
- **C compiler**: GCC or Clang
- **Build tools**:
  - macOS: `xcode-select --install`
  - Linux: `sudo apt-get install build-essential`
  - Windows: [MinGW](http://www.mingw.org/) or [MSVC Build Tools](https://visualstudio.microsoft.com/downloads/)

## 🔧 What Gets Installed

### Executable Location

The `blackbox_decode` executable will be installed to one of these locations (in order of preference):

1. `/usr/local/bin` (most common on macOS/Linux)
2. `/opt/local/bin` (MacPorts)
3. `~/.local/bin` (user directory, no sudo required)
4. `/usr/bin` (system directory)

### Automatic PATH Configuration

If installed to `~/.local/bin`, the script will guide you to add it to your PATH:

```bash
# Add this line to ~/.zshrc, ~/.bash_profile, or ~/.bashrc:
export PATH="$HOME/.local/bin:$PATH"
```

## ✅ Verification

After installation, verify it worked:

```bash
blackbox_decode --help
```

You should see the help output from the blackbox_decode tool.

## 🧹 Cleanup

The script automatically removes:

- ❌ `.git` directory
- ❌ `.github` directory  
- ❌ `test` directories
- ❌ `.html` files
- ❌ Unnecessary `.md` files
- ❌ `vite.config.js`, `package.json`

Kept files:

- ✅ `obj/` - Compiled objects
- ✅ `src/` - Source code
- ✅ `lib/` - Libraries
- ✅ `Makefile`
- ✅ `README.md`
- ✅ `LICENSE`

## 🐛 Troubleshooting

### "git not found"

**macOS**:
```bash
xcode-select --install
```

**Linux**:
```bash
sudo apt-get install git
```

**Windows**: Download from [git-scm.com](https://git-scm.com/download/win)

### "make not found"

**macOS**:
```bash
xcode-select --install
```

**Linux**:
```bash
sudo apt-get install build-essential
```

**Windows**: Install [MinGW](http://www.mingw.org/) or [MSVC](https://visualstudio.microsoft.com/downloads/)

### Compilation fails

Common causes:
1. Missing development headers
2. Incompatible compiler version
3. Missing dependencies

**Solution**:
```bash
# Clean and try again
cd Open-Tuning-Tool
make -C obj clean
python3 tools/blackbox_setup/install_blackbox.py
```

### "Permission denied" when installing

If installation fails due to permissions:

```bash
# Try with sudo
sudo python3 tools/blackbox_setup/install_blackbox.py

# Or install to user directory (no sudo needed)
mkdir -p ~/.local/bin
# Run script and it will auto-install to ~/.local/bin
```

## 📊 Script Features

### Color-Coded Output

- 🟢 **Green** - Success messages
- 🔵 **Blue** - Info messages
- 🟠 **Orange** - Warnings
- 🔴 **Red** - Errors

### Automatic OS Detection

- Detects macOS, Linux, Windows
- Identifies architecture (x86_64, ARM, etc.)

### Timeout Protection

- 5-second timeout for verification
- 300-second timeout for compilation
- Prevents hanging on stalled builds

## 🔒 Security

- Uses only official Betaflight repository
- Shallow clone (--depth 1) for faster downloads
- Verifies executable after installation
- No external scripts executed

## 📝 Advanced Usage

### Manual Installation

If the script fails, install manually:

```bash
# Clone repository
git clone --depth 1 https://github.com/betaflight/blackbox-log-viewer.git
cd blackbox-log-viewer

# Compile
make

# Install
sudo cp obj/blackbox_decode /usr/local/bin/

# Verify
blackbox_decode --help
```

### Custom Installation Path

```bash
# Edit the install_blackbox.py script
# Change the find_install_path() function to return your desired path

# Or manually copy after compilation
cp blackbox-log-viewer/obj/blackbox_decode /your/custom/path/
```

## 📞 Support

If you encounter issues:

1. Check the [Betaflight repository](https://github.com/betaflight/blackbox-log-viewer)
2. Review [compilation documentation](https://github.com/betaflight/blackbox-log-viewer/blob/master/Readme.md)
3. Report issues on [GitHub](https://github.com/Necrophillip/Open-Tuning-Tool/issues)

---

**Happy Tuning!** 🚁
