#!/bin/bash

################################################################################
#                                                                              #
#    Blackbox-Tools Automated Installation Script (Bash Version)             #
#                                                                              #
#    This script automates the installation of blackbox-tools for            #
#    Open-Tuning-Tool:                                                       #
#    1. Clones the blackbox-tools repository                                 #
#    2. Detects the operating system                                         #
#    3. Compiles the blackbox_decode executable                              #
#    4. Moves it to system PATH                                              #
#    5. Verifies the installation                                            #
#    6. Cleans up unnecessary files                                          #
#                                                                              #
#    Author: Open-Tuning-Tool Contributors                                   #
#    License: MIT                                                             #
#                                                                              #
################################################################################

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Functions for colored output
print_header() {
    echo -e "${CYAN}${BOLD}==================================================================${NC}"
    echo -e "${CYAN}${BOLD}$1${NC}"
    echo -e "${CYAN}${BOLD}==================================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Print banner
print_banner() {
    clear
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "    ╔═══════════════════════════════════════════════════════════╗"
    echo "    ║                                                           ║"
    echo "    ║  🚁 Blackbox-Tools Automated Installation Script 🚁      ║"
    echo "    ║                                                           ║"
    echo "    ║        Open-Tuning-Tool Setup Assistant                 ║"
    echo "    ║                                                           ║"
    echo "    ╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macOS"
        ARCH=$(uname -m)
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="Linux"
        ARCH=$(uname -m)
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        OS="Windows"
        ARCH=$(uname -m)
    else
        OS="Unknown"
        ARCH=$(uname -m)
    fi
    
    print_info "Detected OS: ${OS} (${ARCH})"
}

# Check for required tools
check_requirements() {
    print_info "Checking for required tools..."
    
    local missing=false
    
    # Check git
    if ! command -v git &> /dev/null; then
        print_error "git not found"
        missing=true
    else
        print_success "git found"
    fi
    
    # Check make
    if ! command -v make &> /dev/null; then
        print_error "make not found"
        missing=true
    else
        print_success "make found"
    fi
    
    # Check compiler
    if ! command -v gcc &> /dev/null && ! command -v clang &> /dev/null; then
        print_error "C compiler not found (gcc or clang required)"
        missing=true
    else
        print_success "C compiler found"
    fi
    
    if [ "$missing" = true ]; then
        print_warning "Please install missing tools:"
        if [[ "$OS" == "macOS" ]]; then
            echo "  macOS: xcode-select --install"
        elif [[ "$OS" == "Linux" ]]; then
            echo "  Linux: sudo apt-get install build-essential git"
        else
            echo "  Windows: Install MinGW or MSVC Build Tools"
        fi
        exit 1
    fi
}

# Clone repository
clone_repository() {
    print_info "📥 Cloning blackbox-tools repository..."
    
    local temp_dir=$(mktemp -d)
    local repo_url="https://github.com/betaflight/blackbox-log-viewer.git"
    local repo_path="${temp_dir}/blackbox-tools"
    
    if git clone --depth 1 "$repo_url" "$repo_path" > /dev/null 2>&1; then
        print_success "Repository cloned successfully"
        echo "$repo_path"
    else
        print_error "Failed to clone repository"
        exit 1
    fi
}

# Compile blackbox
compile_blackbox() {
    local repo_path="$1"
    
    print_info "🔨 Compiling blackbox_decode..."
    
    if [ ! -f "${repo_path}/Makefile" ]; then
        print_error "Makefile not found"
        return 1
    fi
    
    if make -C "$repo_path" > /dev/null 2>&1; then
        print_success "Compilation successful"
        
        # Find executable
        if [ -f "${repo_path}/obj/blackbox_decode" ]; then
            echo "${repo_path}/obj/blackbox_decode"
        else
            print_error "Executable not found after compilation"
            return 1
        fi
    else
        print_error "Compilation failed"
        return 1
    fi
}

# Find install path
find_install_path() {
    local preferred_paths=(
        "/usr/local/bin"
        "/opt/local/bin"
        "${HOME}/.local/bin"
        "/usr/bin"
    )
    
    for path in "${preferred_paths[@]}"; do
        if [ -d "$path" ] && [ -w "$path" ]; then
            echo "$path"
            return 0
        fi
    done
    
    # Create ~/.local/bin if nothing else works
    mkdir -p "${HOME}/.local/bin"
    echo "${HOME}/.local/bin"
}

# Install executable
install_executable() {
    local exe_path="$1"
    local target_name="blackbox_decode"
    
    print_info "📦 Installing to system PATH..."
    
    local install_path=$(find_install_path)
    local target_path="${install_path}/${target_name}"
    
    if cp "$exe_path" "$target_path"; then
        chmod +x "$target_path"
        print_success "Installed to: ${target_path}"
        return 0
    else
        print_error "Installation failed"
        print_warning "Try: sudo cp $exe_path $target_path"
        return 1
    fi
}

# Verify installation
verify_installation() {
    print_info "✓ Verifying installation..."
    
    if command -v blackbox_decode &> /dev/null; then
        print_success "blackbox_decode is installed and accessible"
        return 0
    else
        print_error "blackbox_decode not found in PATH"
        return 1
    fi
}

# Cleanup repository
cleanup_repository() {
    local repo_path="$1"
    
    print_info "🧹 Cleaning up unnecessary files..."
    
    # Remove directories
    rm -rf "${repo_path}/.git"
    rm -rf "${repo_path}/.github"
    rm -rf "${repo_path}/test"
    
    # Remove files
    find "${repo_path}" -maxdepth 1 -name "*.html" -delete
    find "${repo_path}" -maxdepth 1 -name "*.md" ! -name "README.md" -delete
    find "${repo_path}" -maxdepth 1 -name "package.json" -delete
    find "${repo_path}" -maxdepth 1 -name "vite.config.js" -delete
    find "${repo_path}" -maxdepth 1 -name ".gitignore" -delete
    
    print_success "Cleanup completed"
}

# Main installation process
main() {
    print_banner
    
    # Detect OS
    detect_os
    echo ""
    
    # Check requirements
    check_requirements
    echo ""
    
    # Create temporary directory
    local temp_dir=$(mktemp -d)
    print_info "Using temporary directory: ${temp_dir}"
    echo ""
    
    # Clone repository
    local repo_path=$(clone_repository)
    echo ""
    
    # Compile executable
    local exe_path=$(compile_blackbox "$repo_path")
    if [ $? -ne 0 ]; then
        print_error "Installation failed: Compilation error"
        rm -rf "$temp_dir"
        exit 1
    fi
    echo ""
    
    # Install executable
    if ! install_executable "$exe_path"; then
        print_warning "Manual installation required"
        rm -rf "$temp_dir"
        exit 1
    fi
    echo ""
    
    # Clean up repository
    cleanup_repository "$repo_path"
    echo ""
    
    # Verify installation
    if ! verify_installation; then
        print_warning "Installation may require additional setup"
        print_info "Add to your PATH (~/.zshrc, ~/.bash_profile, or ~/.bashrc):"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        rm -rf "$temp_dir"
        exit 1
    fi
    echo ""
    
    # Cleanup temp directory
    rm -rf "$temp_dir"
    
    # Success message
    print_success "============================================================"
    print_success "✓ Blackbox-Tools installation completed successfully!"
    print_success "============================================================"
    echo ""
    print_info "You can now use Open-Tuning-Tool with binary log files."
    print_info "Run: cd Open-Tuning-Tool && python3 -m fpv_tuner.main"
    echo ""
}

# Run main function
main
