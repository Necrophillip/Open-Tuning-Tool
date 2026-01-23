#!/usr/bin/env python3
"""
Automated Blackbox-Tools Installation Script

This script automates the installation of blackbox-tools for Open-Tuning-Tool:
1. Clones the blackbox-tools repository
2. Detects the operating system (macOS, Linux, or Windows)
3. Compiles the blackbox_decode executable
4. Moves it to system PATH
5. Verifies the installation
6. Cleans up unnecessary files

Author: Open-Tuning-Tool Contributors
License: MIT
"""

import os
import sys
import platform
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Tuple, Optional

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @staticmethod
    def header(text: str) -> str:
        return f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}"
    
    @staticmethod
    def success(text: str) -> str:
        return f"{Colors.OKGREEN}{text}{Colors.ENDC}"
    
    @staticmethod
    def error(text: str) -> str:
        return f"{Colors.FAIL}{text}{Colors.ENDC}"
    
    @staticmethod
    def warning(text: str) -> str:
        return f"{Colors.WARNING}{text}{Colors.ENDC}"
    
    @staticmethod
    def info(text: str) -> str:
        return f"{Colors.OKCYAN}{text}{Colors.ENDC}"


def print_banner():
    """Display installation banner"""
    banner = r"""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║    🚁 Blackbox-Tools Automated Installation Script 🚁    ║
    ║                                                           ║
    ║           Open-Tuning-Tool Setup Assistant              ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(Colors.header(banner))


def detect_os() -> Tuple[str, str]:
    """
    Detect the operating system
    
    Returns:
        Tuple of (os_name, architecture)
    """
    system = platform.system()
    arch = platform.machine()
    
    if system == "Darwin":
        os_name = "macOS"
    elif system == "Linux":
        os_name = "Linux"
    elif system == "Windows":
        os_name = "Windows"
    else:
        os_name = system
    
    print(Colors.info(f"✓ Detected OS: {os_name} ({arch})"))
    return os_name, arch


def clone_repository(temp_dir: str) -> str:
    """
    Clone the blackbox-tools repository
    
    Args:
        temp_dir: Temporary directory path
        
    Returns:
        Path to cloned repository
    """
    print(Colors.info("\n📥 Cloning blackbox-tools repository..."))
    
    repo_url = "https://github.com/betaflight/blackbox-log-viewer.git"
    repo_path = os.path.join(temp_dir, "blackbox-tools")
    
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, repo_path],
            check=True,
            capture_output=True
        )
        print(Colors.success("✓ Repository cloned successfully"))
        return repo_path
    except subprocess.CalledProcessError as e:
        print(Colors.error(f"✗ Failed to clone repository: {e}"))
        sys.exit(1)
    except FileNotFoundError:
        print(Colors.error("✗ git not found. Please install git and try again."))
        sys.exit(1)


def compile_blackbox(repo_path: str, os_name: str) -> Optional[str]:
    """
    Compile blackbox_decode executable
    
    Args:
        repo_path: Path to blackbox-tools repository
        os_name: Operating system name
        
    Returns:
        Path to compiled executable or None if failed
    """
    print(Colors.info("\n🔨 Compiling blackbox_decode..."))
    
    src_dir = os.path.join(repo_path, "src")
    obj_dir = os.path.join(repo_path, "obj")
    
    if not os.path.exists(src_dir):
        print(Colors.error("✗ Source directory not found"))
        return None
    
    # Check for Makefile
    makefile = os.path.join(repo_path, "Makefile")
    if not os.path.exists(makefile):
        print(Colors.error("✗ Makefile not found"))
        return None
    
    try:
        # Run make
        subprocess.run(
            ["make", "-C", repo_path],
            check=True,
            capture_output=True,
            timeout=300
        )
        
        # Find compiled executable
        if os.path.exists(obj_dir):
            for item in os.listdir(obj_dir):
                item_path = os.path.join(obj_dir, item)
                if os.path.isfile(item_path) and "blackbox_decode" in item.lower():
                    print(Colors.success("✓ Compilation successful"))
                    return item_path
        
        print(Colors.error("✗ Executable not found after compilation"))
        return None
        
    except subprocess.CalledProcessError as e:
        print(Colors.error(f"✗ Compilation failed: {e}"))
        return None
    except FileNotFoundError:
        print(Colors.error("✗ make not found. Please install build tools:"))
        print(Colors.warning("  macOS: xcode-select --install"))
        print(Colors.warning("  Linux: sudo apt-get install build-essential"))
        return None
    except subprocess.TimeoutExpired:
        print(Colors.error("✗ Compilation timed out"))
        return None


def find_install_path() -> str:
    """
    Find the best installation path in system PATH
    
    Returns:
        Installation path
    """
    # Preferred paths in order
    preferred_paths = [
        "/usr/local/bin",
        "/opt/local/bin",
        os.path.expanduser("~/.local/bin"),
        "/usr/bin",
    ]
    
    # Check which paths exist and are writable
    for path in preferred_paths:
        if os.path.exists(path):
            try:
                # Test if writable
                test_file = os.path.join(path, ".write_test")
                Path(test_file).touch()
                os.remove(test_file)
                return path
            except (OSError, PermissionError):
                continue
    
    # Create ~/.local/bin if nothing else works
    local_bin = os.path.expanduser("~/.local/bin")
    os.makedirs(local_bin, exist_ok=True)
    return local_bin


def install_executable(exe_path: str, target_name: str = "blackbox_decode") -> bool:
    """
    Install executable to system PATH
    
    Args:
        exe_path: Path to the compiled executable
        target_name: Name to give the executable
        
    Returns:
        True if successful, False otherwise
    """
    print(Colors.info(f"\n📦 Installing to system PATH..."))
    
    install_path = find_install_path()
    target_path = os.path.join(install_path, target_name)
    
    try:
        # Copy executable
        shutil.copy2(exe_path, target_path)
        
        # Make executable
        os.chmod(target_path, 0o755)
        
        print(Colors.success(f"✓ Installed to: {target_path}"))
        return True
        
    except (OSError, PermissionError) as e:
        print(Colors.error(f"✗ Installation failed: {e}"))
        print(Colors.warning(f"  Try: sudo cp {exe_path} {target_path}")
              .format(exe_path=exe_path, target_path=target_path))
        return False


def verify_installation() -> bool:
    """
    Verify that blackbox_decode is installed and accessible
    
    Returns:
        True if verified, False otherwise
    """
    print(Colors.info("\n✓ Verifying installation..."))
    
    try:
        result = subprocess.run(
            ["blackbox_decode", "--help"],
            capture_output=True,
            timeout=5
        )
        
        if result.returncode == 0:
            print(Colors.success("✓ blackbox_decode is installed and accessible"))
            return True
        else:
            print(Colors.error("✗ blackbox_decode found but verification failed"))
            return False
            
    except FileNotFoundError:
        print(Colors.error("✗ blackbox_decode not found in PATH"))
        return False
    except subprocess.TimeoutExpired:
        print(Colors.error("✗ Verification timed out"))
        return False


def cleanup_repository(repo_path: str) -> None:
    """
    Clean up unnecessary files from the repository
    
    Args:
        repo_path: Path to the repository
    """
    print(Colors.info("\n🧹 Cleaning up unnecessary files..."))
    
    # Files and directories to keep
    keep_items = {"obj", "src", "lib", "Makefile", "README.md", "LICENSE"}
    
    # Items to remove
    items_to_remove = [
        "test",
        ".git",
        ".github",
        ".gitignore",
        "public",
        "vite.config.js",
        "package.json",
        "*.html",
        "*.md",
        "changelog.html",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
    ]
    
    try:
        for item in os.listdir(repo_path):
            item_path = os.path.join(repo_path, item)
            
            # Remove .git directory
            if item == ".git" and os.path.isdir(item_path):
                shutil.rmtree(item_path)
                print(Colors.info(f"  Removed: {item}")
                continue
            
            # Remove .github directory
            if item == ".github" and os.path.isdir(item_path):
                shutil.rmtree(item_path)
                print(Colors.info(f"  Removed: {item}"))
                continue
            
            # Remove test directory
            if item == "test" and os.path.isdir(item_path):
                shutil.rmtree(item_path)
                print(Colors.info(f"  Removed: {item}"))
                continue
            
            # Remove HTML files
            if item.endswith(".html"):
                os.remove(item_path)
                print(Colors.info(f"  Removed: {item}"))
                continue
            
            # Remove unnecessary MD files
            if item.endswith(".md") and item != "README.md":
                os.remove(item_path)
                print(Colors.info(f"  Removed: {item}"))
                continue
        
        print(Colors.success("✓ Cleanup completed"))
        
    except (OSError, PermissionError) as e:
        print(Colors.warning(f"⚠ Cleanup partially failed: {e}"))


def main():
    """Main installation process"""
    print_banner()
    
    # Detect OS
    os_name, arch = detect_os()
    
    # Check for required tools
    print(Colors.info("\n🔍 Checking for required tools..."))
    
    required_tools = ["git", "make"]
    for tool in required_tools:
        try:
            subprocess.run(
                [tool, "--version"],
                capture_output=True,
                timeout=5
            )
            print(Colors.success(f"✓ {tool} found"))
        except FileNotFoundError:
            print(Colors.error(f"✗ {tool} not found"))
            print(Colors.warning(f"  Please install {tool} and try again"))
            if os_name == "macOS":
                print(Colors.warning("  macOS: brew install " + tool))
            elif os_name == "Linux":
                print(Colors.warning(f"  Linux: sudo apt-get install {tool}"))
            return False
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        print(Colors.info(f"\n📁 Using temporary directory: {temp_dir}"))
        
        # Clone repository
        repo_path = clone_repository(temp_dir)
        
        # Compile executable
        exe_path = compile_blackbox(repo_path, os_name)
        if not exe_path:
            print(Colors.error("✗ Installation failed: Compilation error"))
            return False
        
        # Install executable
        if not install_executable(exe_path, "blackbox_decode"):
            print(Colors.warning("⚠ Manual installation required"))
            return False
        
        # Clean up repository
        cleanup_repository(repo_path)
    
    # Verify installation
    if not verify_installation():
        print(Colors.warning("⚠ Installation may require additional setup"))
        print(Colors.info("  Make sure ~/.local/bin is in your PATH:")
              .format())
        print(Colors.warning('  export PATH="$HOME/.local/bin:$PATH"'))
        return False
    
    # Success
    print(Colors.success("\n" + "="*60))
    print(Colors.success("✓ Blackbox-Tools installation completed successfully!"))
    print(Colors.success("="*60))
    print(Colors.info("\nYou can now use Open-Tuning-Tool with binary log files."))
    print(Colors.info("Run: cd Open-Tuning-Tool && python3 -m fpv_tuner.main\n"))
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
