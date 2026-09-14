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

import logging
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

logger = logging.getLogger(__name__)

BBL_EXTENSIONS = (".bbl", ".bfl")


class MassStorageError(RuntimeError):
    """Raised when mass-storage / extraction fails."""


def default_extraction_dir() -> str:
    """
    Return the default destination for extracted blackbox files.

    Uses ``~/.fpv_tuner/extracted`` — a dot-directory that is writable
    without macOS TCC prompts (unlike ``~/Downloads`` / ``~/Documents``).
    """
    d = Path.home() / ".fpv_tuner" / "extracted"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


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
    logger.info("Waiting up to %.0fs for a new mount point...", timeout)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = set(find_mount_points())
        new = sorted(current - baseline)
        if new:
            logger.info("New mount appeared after %.1fs", timeout - (deadline - time.monotonic()))
            return new
        time.sleep(interval)
    logger.warning("No new mount point detected within %.0fs", timeout)
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


def locate_bbl_files_with_retry(
    mount_path: str, timeout: float = 10.0, interval: float = 0.5,
) -> list[str]:
    """
    Like ``locate_bbl_files`` but retries for ``timeout`` seconds.

    The FAT flash filesystem can take a moment to enumerate its files after
    the volume is first mounted, so an immediate scan may return nothing.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = locate_bbl_files(mount_path)
        if found:
            logger.info("Found %d BBL file(s) after %.1fs: %s",
                        len(found), timeout - (deadline - time.monotonic()), found)
            return found
        time.sleep(interval)
    logger.warning("No BBL files found on %s within %.0fs", mount_path, timeout)
    return []


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
        
        counter = 1
        base_name = f"{src_path.stem}_{int(src_path.stat().st_mtime_ns)}"
        while target.exists():
            target = dest / f"{base_name}_{counter}{src_path.suffix}"
            counter += 1
            
        # Use copy instead of copy2 so we don't copy macOS uchg (FAT Read-Only) flags
        shutil.copy(src_path, target)
        
        # Ensure the copied file is writable by the user
        try:
            os.chmod(target, 0o644)
        except OSError:
            pass
            
        copied.append(str(target))
    return copied


def copy_blackbox_file(source_path: str, dest_dir: str) -> str:
    """Copy a single blackbox file into ``dest_dir``; return the new path."""
    return copy_bbl_files([source_path], dest_dir)[0]


def filter_blackbox_files(paths: list[str]) -> list[str]:
    """
    Remove the "all" combined blackbox file(s) from a list of paths.

    Betaflight boards often produce a ``*_all.bbl`` file that concatenates
    every arm/disarm session, alongside per-flight fragments.  We exclude
    any file whose name contains "all" so the user picks a single flight.
    """
    return [p for p in paths if "all" not in Path(p).stem.lower()]


def eject(mount_path: str) -> bool:
    """
    Best-effort eject of a mounted volume so the FC reboots to firmware.

    Tries the mount path first, then falls back to the backing disk device.
    Returns True if any eject/unmount command succeeded.

    Note: some flight controllers stay in mass-storage mode until the USB
    cable is physically re-plugged, regardless of a software eject.  Callers
    should treat a ``False``/remount as a hint to ask the user to reconnect.
    """
    try:
        if sys.platform == "darwin":
            for target in (mount_path, _disk_device_for_mount(mount_path)):
                if not target:
                    continue
                if _run_eject(["diskutil", "eject", target]):
                    return True
                if _run_eject(["diskutil", "unmountDisk", "force", target]):
                    return True
            return False
        elif sys.platform.startswith("linux"):
            dev = _disk_device_for_mount(mount_path) or mount_path
            return _run_eject(["udisksctl", "unmount", "-b", dev])
        # Windows: ejecting requires more work; the user can safely remove.
        return False
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return False


def _run_eject(cmd: list[str]) -> bool:
    """Run an eject/unmount command; True on success (exit code 0)."""
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=20)
        return True
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return False


def _disk_device_for_mount(mount_path: str) -> Optional[str]:
    """
    Resolve a mount point to its backing device (e.g. ``/dev/disk4``).

    Returns None if it cannot be determined.
    """
    try:
        if sys.platform == "darwin":
            out = subprocess.run(
                ["diskutil", "info", "-plist", mount_path],
                capture_output=True, text=True, timeout=10,
            )
            if out.returncode != 0:
                return None
            import plistlib
            info = plistlib.loads(out.stdout.encode("utf-8"))
            dev = info.get("ParentWholeDisk") or info.get("DeviceIdentifier")
            return f"/dev/{dev}" if dev else None
        elif sys.platform.startswith("linux"):
            out = subprocess.run(
                ["findmnt", "-no", "SOURCE", mount_path],
                capture_output=True, text=True, timeout=10,
            )
            if out.returncode == 0:
                return out.stdout.strip() or None
        return None
    except (subprocess.SubprocessError, OSError, ImportError, ValueError):
        return None


# ── Orchestration ─────────────────────────────────────────────────

def enter_mass_storage(port: str, baudrate: int = 115200) -> None:
    """Reboot the FC into USB mass-storage mode over MSP."""
    logger.info("enter_mass_storage: port=%s baud=%d", port, baudrate)
    with SerialConnection(port, baudrate=baudrate) as conn:
        client = MspClient(conn)
        # Pre-flight: confirm the FC is responsive before rebooting. A freshly
        # reconnected FC may still be booting and would drop the reboot.
        for attempt in range(3):
            try:
                client.api_version()
                break
            except Exception as exc:
                logger.warning("Pre-flight MSP ping failed (attempt %d): %s", attempt + 1, exc)
                time.sleep(0.5)
        else:
            raise MassStorageError("Flight controller is not responding to MSP — is it connected?")
        logger.info("FC responsive; requesting mass-storage mode")
        client.reboot_to_mass_storage()
    logger.info("MSP reboot sent; waiting for the FC to re-enumerate as MSC")


def enter_and_list_blackbox(
    port: str,
    baudrate: int = 115200,
    mount_timeout: float = 30.0,
) -> tuple[str, list[str]]:
    """
    Enter mass-storage mode and list the blackbox files (excluding "all").

    Returns:
        ``(mount_point, files)`` where ``files`` are non-"all" ``.bbl`` paths.
        Falls back to the full file list if the volume only contains the
        combined "all" file.
    """
    before = find_mount_points()
    logger.info("Mount points before: %s", before)
    enter_mass_storage(port, baudrate=baudrate)

    new_mounts = wait_for_mount(timeout=mount_timeout, before=before)
    logger.info("New mount points: %s", new_mounts)
    if not new_mounts:
        raise MassStorageError(
            "No new volume appeared after entering mass-storage mode. "
            "Try again, or check the USB connection."
        )

    mount_point = new_mounts[0]
    raw = locate_bbl_files_with_retry(mount_point, timeout=8.0)
    # Prefer a mount that has per-flight files (not just the "all" file).
    for mp in new_mounts[1:]:
        mp_raw = locate_bbl_files_with_retry(mp, timeout=8.0)
        if filter_blackbox_files(mp_raw):
            mount_point = mp
            raw = mp_raw
            break

    filtered = filter_blackbox_files(raw)
    if not filtered:
        logger.info("Only 'all' blackbox file(s) present; using them as fallback")
        filtered = raw

    logger.info("Blackbox files available: %s", filtered)
    return mount_point, filtered


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
    logger.info("Mount points before: %s", before)
    enter_mass_storage(port, baudrate=baudrate)

    new_mounts = wait_for_mount(timeout=mount_timeout, before=before)
    logger.info("New mount points: %s", new_mounts)
    if not new_mounts:
        raise MassStorageError(
            "No new volume appeared after entering mass-storage mode. "
            "Try again, or check the USB connection."
        )

    # Prefer the mount that actually contains a blackbox log (with retry,
    # since the FAT filesystem may take a moment to enumerate).
    mount_point = None
    bbl_files = []
    for mp in new_mounts:
        files = locate_bbl_files_with_retry(mp, timeout=8.0)
        if files:
            mount_point = mp
            bbl_files = files
            break
    if mount_point is None:
        mount_point = new_mounts[0]
        bbl_files = locate_bbl_files_with_retry(mount_point, timeout=8.0)
    logger.info("Selected mount point: %s", mount_point)

    if not bbl_files:
        raise MassStorageError(
            f"No .BBL files found on the mounted volume '{mount_point}'."
        )

    copied = copy_bbl_files(bbl_files, dest_dir)
    logger.info("Copied %d file(s) to %s: %s", len(copied), dest_dir, copied)

    ejected = False
    if eject_after:
        ejected = eject(mount_point)
        logger.info("Eject %s -> %s", mount_point, ejected)

    return {
        "bbl_files": copied,
        "mount_point": mount_point,
        "ejected": ejected,
    }
