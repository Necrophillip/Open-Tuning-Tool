"""
CLI Diff Generator — human-readable comparison of CLI dumps.

Pure Python, no Qt.  Compares two sets of CLI settings (or a dump
vs. a prescription) and produces a clear, readable diff that the
user can review before applying changes.
"""
from dataclasses import dataclass, field
from typing import Optional

from fpv_tuner.core.prescription import Prescription, PrescribedChange


@dataclass
class DiffEntry:
    """One line in the diff."""
    setting: str
    old_value: str
    new_value: str
    kind: str            # "changed" | "added" | "removed"
    reason: str = ""     # why (from prescription)


@dataclass
class CliDiff:
    """Complete diff between two CLI states."""
    entries: list[DiffEntry] = field(default_factory=list)
    summary: str = ""

    @property
    def has_changes(self) -> bool:
        return bool(self.entries)

    @property
    def n_changes(self) -> int:
        return len(self.entries)


def diff_settings(
    original: dict[str, str],
    modified: dict[str, str],
) -> CliDiff:
    """
    Compare two settings dicts and produce a diff.

    Args:
        original: Current settings {name: value}.
        modified: New settings {name: value}.

    Returns:
        CliDiff with all differences.
    """
    diff = CliDiff()
    all_keys = sorted(set(original) | set(modified))

    for key in all_keys:
        old = original.get(key)
        new = modified.get(key)

        if old == new:
            continue
        elif old is None:
            diff.entries.append(DiffEntry(
                setting=key, old_value="", new_value=new, kind="added",
            ))
        elif new is None:
            diff.entries.append(DiffEntry(
                setting=key, old_value=old, new_value="", kind="removed",
            ))
        else:
            diff.entries.append(DiffEntry(
                setting=key, old_value=old, new_value=new, kind="changed",
            ))

    diff.summary = f"{len(diff.entries)} setting(s) changed"
    return diff


def diff_from_prescription(
    current_settings: Optional[dict[str, str]],
    prescription: Prescription,
) -> CliDiff:
    """
    Create a diff from a prescription.

    Args:
        current_settings: Current CLI dump settings (or None).
        prescription:     Output of generate_prescription().

    Returns:
        CliDiff ready for display.
    """
    diff = CliDiff()

    for change in prescription.changes:
        diff.entries.append(DiffEntry(
            setting=change.setting,
            old_value=change.old_value,
            new_value=change.new_value,
            kind="changed",
            reason=change.reason,
        ))

    if diff.entries:
        diff.summary = (
            f"{len(diff.entries)} change(s) recommended "
            f"({len(prescription.notes)} note(s))"
        )
    else:
        diff.summary = "No changes recommended"

    return diff


def format_diff_text(diff: CliDiff) -> str:
    """
    Format a CliDiff as human-readable plain text.

    Suitable for display in a QPlainTextEdit or copying to clipboard.
    """
    if not diff.has_changes:
        return "No changes — your configuration looks good!\n"

    lines = [
        f"FPV Tuner — Recommended Changes",
        f"{'=' * 40}",
        "",
    ]

    for entry in diff.entries:
        if entry.kind == "changed":
            lines.append(f"  {entry.setting}")
            lines.append(f"    - old: {entry.old_value}")
            lines.append(f"    + new: {entry.new_value}")
            if entry.reason:
                lines.append(f"    > {entry.reason}")
            lines.append("")
        elif entry.kind == "added":
            lines.append(f"  {entry.setting} = {entry.new_value}  (new)")
            if entry.reason:
                lines.append(f"    > {entry.reason}")
            lines.append("")
        elif entry.kind == "removed":
            lines.append(f"  {entry.setting}  (removed, was {entry.old_value})")
            lines.append("")

    lines.append(f"{'─' * 40}")
    lines.append(f"Total: {diff.n_changes} change(s)")
    return "\n".join(lines)


def format_diff_html(diff: CliDiff) -> str:
    """
    Format a CliDiff as simple HTML for rich-text display.

    Suitable for QLabel with setTextFormat(RichText).
    """
    if not diff.has_changes:
        return (
            "<span style='color:#3DDC84;'>✅ No changes — "
            "your configuration looks good!</span>"
        )

    parts = [f"<b>{diff.summary}</b><br><br>"]

    for entry in diff.entries:
        if entry.kind == "changed":
            parts.append(
                f"<b>{entry.setting}</b><br>"
                f"&nbsp;&nbsp;<span style='color:#FF5C5C;'>- {entry.old_value}</span><br>"
                f"&nbsp;&nbsp;<span style='color:#3DDC84;'>+ {entry.new_value}</span><br>"
            )
            if entry.reason:
                parts.append(
                    f"&nbsp;&nbsp;<i style='color:#8B949E;'>{entry.reason}</i><br>"
                )
            parts.append("<br>")
        elif entry.kind == "added":
            parts.append(
                f"<b>{entry.setting}</b> = {entry.new_value} "
                f"<span style='color:#4CC2FF;'>(new)</span><br><br>"
            )
        elif entry.kind == "removed":
            parts.append(
                f"<b>{entry.setting}</b> "
                f"<span style='color:#FF5C5C;'>(removed)</span><br><br>"
            )

    return "".join(parts)


def format_cli_commands(diff: CliDiff) -> str:
    """
    Format as Betaflight CLI commands ready to paste.

    Returns lines like:
        set gyro_lowpass_hz = 150
        save
    """
    if not diff.has_changes:
        return "# No changes needed\n"

    lines = ["# FPV Tuner — Recommended changes", ""]
    for entry in diff.entries:
        if entry.kind == "changed":
            lines.append(f"set {entry.setting} = {entry.new_value}")
        elif entry.kind == "added":
            lines.append(f"set {entry.setting} = {entry.new_value}")
        elif entry.kind == "removed":
            lines.append(f"# Removed: set {entry.setting} = {entry.old_value}")
    lines.append("save")
    return "\n".join(lines)
