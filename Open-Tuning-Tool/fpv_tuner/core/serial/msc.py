"""
Mass-storage mode (MSC) + Blackbox (.BBL) extraction.

Pure Python, no Qt.  The standard way to pull a blackbox log off a
Betaflight flight controller is to reboot it into USB mass-storage mode
(via ``MSP_REBOOT``), wait for the flash to mount as a drive, then copy
the ``.BBL`` file(s).

This module orchestrates that flow and provides the small pieces the UI
needs (enter MSC, wait for mount, locate/copy files, eject).
"""
from __future__ import annotations

import os
import shutil
import string
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from fpv_tuner.core.serial.connection import SerialConnection
from fpv_tuner.core.serial.msp import MspClient

BBL_EXTENSIONS = (".bbl", ".bfl")


class MassStorageError(RuntimeError):
    """Raised when mass-storage / extraction fails."""


# ── Mount point discovery ─────────────────────────────────────────

def find_mount_points() -> list[str]:
    """Return currently mounted removable/volume paths (best effort)."""
    points: list[str] = []

    if sys.platform == "darwin":
        vol = Path("/Volumes")
        if vol.exists():
            points.extend(str(p) for p in vol.iterdir() if p.is_dir())

    elif sys.platform.startswith("linux"):
        user = os.environ.get("USER", "")
        roots = [
            Path("/media") / user,
            Path("/media"),
            Path("/run/media") / user,
            Path("/mnt"),
        ]
        seen = set()
        for root in roots:
            if not root.exists():
                continue
            for p in root.iterdir():
                if p.is_dir() and str(p) not in seen:
                    seen.add(str(p))
                    points.append(str(p))

    elif sys.platform.startswith("win"):
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:\\")
            if drive.exists():
                points.append(str(drive))

    return points


def wait_for_mount(
    timeout: float = 30.0,
    interval: float = 0.5,
    before: Optional[list[str]] = None,
) -> list[str]:
    """
    Poll for a *new* mount point to appear.

    Args:
        timeout:  How long to wait (seconds).
        interval: Poll interval (seconds).
        before:   Mount points that already existed (ignored).

    Returns:
        List of newly appeared mount paths (possibly empty on timeout).
    """
    baseline = set(before or [])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = set(find_mount_points())
        new = sorted(current - baseline)
        if new:
            return new
        time.sleep(interval)
    return []


# ── Blackbox file discovery ───────────────────────────────────────

def locate_bbl_files(mount_path: str, max_depth: int = 3) -> list[str]:
    """
    Find ``.BBL``/``.BFL`` files under a mounted volume (case-insensitive).

    Returns paths sorted by modification time (newest first).
    """
    root = Path(mount_path)
    found = []
    for path in _walk(root, depth=max_depth):
        if path.is_file() and path.suffix.lower() in BBL_EXTENSIONS:
            found.append(path)
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p) for p in found]


def _walk(root: Path, depth: int, current: int = 0):
    if current > depth:
        return
    try:
        for entry in root.iterdir():
            yield entry
            if entry.is_dir() and current < depth:
                yield from _walk(entry, depth, current + 1)
    except (OSError, PermissionError):
        return


def copy_bbl_files(source_paths: list[str], dest_dir: str) -> list[str]:
    """
    Copy blackbox files into ``dest_dir``.

    Collisions are resolved by suffixing a timestamp.  Returns the list of
    destination paths.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in source_paths:
        src_path = Path(src)
        target = dest / src_path.name
        if target.exists():
            target = dest / f"{src_path.stem}_{int(src_path.stat().st_mtime_ns)}{src_path.suffix}"
        shutil.copy2(src_path, target)
        copied.append(str(target))
    return copied


def eject(mount_path: str) -> bool:
    """
    Best-effort eject of a mounted volume so the FC reboots to firmware.

    Returns True on success, False if no method succeeded.
    """
    try:
        if sys.platform == "darwin":
            subprocess.run(["diskutil", "eject", mount_path], check=True,
                           capture_output=True, timeout=20)
            return True
        elif sys.platform.startswith("linux"):
            subprocess.run(["udisksctl", "unmount", "-b", mount_path],
                           check=True, capture_output=True, timeout=20)
            return True
        # Windows: ejecting requires more work; the user can safely remove.
        return False
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return False


# ── Orchestration ─────────────────────────────────────────────────

def enter_mass_storage(port: str, baudrate: int = 115200) -> None:
    """Reboot the FC into USB mass-storage mode over MSP."""
    with SerialConnection(port, baudrate=baudrate) as conn:
        client = MspClient(conn)
        client.reboot_to_mass_storage()


def extract_bbl(
    port: str,
    dest_dir: str,
    baudrate: int = 115200,
    mount_timeout: float = 30.0,
    eject_after: bool = True,
) -> dict:
    """
    Full extraction flow: enter MSC, wait for mount, copy .BBL file(s).

    Returns:
        {"bbl_files": [...], "mount_point": str, "ejected": bool}
    """
    before = find_mount_points()
    enter_mass_storage(port, baudrate=baudrate)

    new_mounts = wait_for_mount(timeout=mount_timeout, before=before)
    if not new_mounts:
        raise MassStorageError(
            "No new volume appeared after entering mass-storage mode. "
            "Try again, or check the USB connection."
        )

    # Prefer the mount that actually contains a blackbox log.
    mount_point = None
    for mp in new_mounts:
        if locate_bbl_files(mp):
            mount_point = mp
            break
    if mount_point is None:
        mount_point = new_mounts[0]

    bbl_files = locate_bbl_files(mount_point)
    if not bbl_files:
        raise MassStorageError(
            f"No .BBL files found on the mounted volume '{mount_point}'."
        )

    copied = copy_bbl_files(bbl_files, dest_dir)

    ejected = False
    if eject_after:
        ejected = eject(mount_point)

    return {
        "bbl_files": copied,
        "mount_point": mount_point,
        "ejected": ejected,
    }
