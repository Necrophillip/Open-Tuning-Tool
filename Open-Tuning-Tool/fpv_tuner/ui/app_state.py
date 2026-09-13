"""
Application State — single source of truth for the wizard flow.

Holds everything the user has loaded and what has been computed,
and notifies pages when something they care about changes.

Pages NEVER talk to each other directly; they read from AppState
and react to its signals.
"""
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
from PyQt6.QtCore import QObject, pyqtSignal


@dataclass
class LogSession:
    """Everything derived from one loaded blackbox log."""
    file_path: str = ""
    dataframe: Optional[pd.DataFrame] = None
    pids: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)
    n_rows: int = 0
    duration_s: float = 0.0
    merged_segments: int = 1


@dataclass
class CliDump:
    """Parsed CLI dump from Betaflight."""
    raw_text: str = ""
    version: str = ""               # e.g. "4.5.0"
    settings: dict = field(default_factory=dict)  # name -> value
    file_path: str = ""


@dataclass
class AnalysisResult:
    """Aggregated results from the automatic analysis pass."""
    completed: bool = False
    summary: str = ""
    # Sprint 2: engine outputs stored for cross-page sharing
    findings: list = field(default_factory=list)       # list[Finding]
    prescription: object = None                         # Prescription
    cli_diff: object = None                             # CliDiff
    session_id: str = ""                                # saved session ID
    # Review page data (step response + noise heatmaps per axis)
    step_responses: dict = field(default_factory=dict)  # axis -> summary dict
    heatmaps: dict = field(default_factory=dict)        # axis -> heatmap dict


class AppState(QObject):
    """
    Central mutable state + change notifications.

    Signals carry no payload; listeners re-read what they need
    from the state object (avoids stale-data bugs).
    """

    log_loaded = pyqtSignal()        # A log session became available
    log_cleared = pyqtSignal()
    cli_loaded = pyqtSignal()        # A CLI dump became available
    cli_cleared = pyqtSignal()
    analysis_updated = pyqtSignal()  # Analysis results changed
    step_changed = pyqtSignal(int)   # Current wizard step index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.log: Optional[LogSession] = None
        self.cli: Optional[CliDump] = None
        self.analysis: Optional[AnalysisResult] = None
        self.current_step: int = 0

    # ── Log session ───────────────────────────────────────────────
    def set_log(self, session: LogSession):
        self.log = session
        # New log invalidates any previous analysis
        self.analysis = None
        self.log_loaded.emit()
        self.analysis_updated.emit()

    def clear_log(self):
        self.log = None
        self.analysis = None
        self.log_cleared.emit()
        self.analysis_updated.emit()

    @property
    def has_log(self) -> bool:
        return self.log is not None and self.log.dataframe is not None

    # ── CLI dump ──────────────────────────────────────────────────
    def set_cli(self, dump: CliDump):
        self.cli = dump
        self.cli_loaded.emit()

    def clear_cli(self):
        self.cli = None
        self.cli_cleared.emit()

    @property
    def has_cli(self) -> bool:
        return self.cli is not None and bool(self.cli.raw_text)

    # ── Analysis ──────────────────────────────────────────────────
    def set_analysis(self, result: AnalysisResult):
        self.analysis = result
        self.analysis_updated.emit()

    @property
    def has_analysis(self) -> bool:
        return self.analysis is not None and self.analysis.completed

    # ── Navigation ────────────────────────────────────────────────
    def set_step(self, index: int):
        if index != self.current_step:
            self.current_step = index
            self.step_changed.emit(index)
