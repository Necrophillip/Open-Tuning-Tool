"""
Job Runner — modern background task execution for the UI.

Replaces the old dedicated-QThread worker pattern with a QThreadPool-based
system that supports:
  - Multiple concurrent jobs
  - Progress reporting (percent + message)
  - Cooperative cancellation
  - Result / error delivery via signals on the main thread

Usage:
    runner = JobRunner(self)
    job_id = runner.run(
        fn=lambda job: load_log(path, merge_all_segments=True),
        on_result=lambda result: ...,
        on_error=lambda msg: ...,
        on_progress=lambda pct, msg: ...,
    )
    # To cancel:
    runner.cancel(job_id)
"""
import traceback
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot


class JobCancelledError(Exception):
    """Raised inside a job function when the job has been cancelled."""


class Job:
    """Handle passed to job functions so they can report progress and
    check for cancellation requests."""

    def __init__(self, signals: "_JobSignals"):
        self._signals = signals

    def report_progress(self, percent: int, message: str = ""):
        """Emit progress from within the job (0-100)."""
        self._signals.progress.emit(percent, message)

    def check_cancelled(self):
        """Call periodically inside long loops. Raises JobCancelledError
        if cancellation was requested."""
        if self._signals.cancel_requested:
            raise JobCancelledError("Job was cancelled by the user.")


class _JobSignals(QObject):
    """Signals for a single job. Lives on the main thread; QRunnable
    emits into it from worker threads (queued connection)."""

    progress = pyqtSignal(int, str)          # percent, message
    result = pyqtSignal(object)              # job return value
    error = pyqtSignal(str)                  # formatted error message
    finished = pyqtSignal()                  # always emitted last

    def __init__(self):
        super().__init__()
        self.cancel_requested = False


class _JobRunnable(QRunnable):
    """Wraps a callable so it can run on the thread pool."""

    def __init__(self, fn, signals: _JobSignals):
        super().__init__()
        self._fn = fn
        self._signals = signals

    @pyqtSlot()
    def run(self):
        job = Job(self._signals)
        try:
            value = self._fn(job)
            self._signals.result.emit(value)
        except JobCancelledError:
            pass  # Silent — the UI already knows it cancelled
        except Exception:
            self._signals.error.emit(traceback.format_exc())
        finally:
            self._signals.finished.emit()


class JobRunner(QObject):
    """Owns the thread pool and tracks active jobs by id."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        # Leave one core free for the UI thread on small machines
        self._pool.setMaxThreadCount(max(1, self._pool.maxThreadCount()))
        self._active: dict[int, _JobSignals] = {}
        self._next_id = 0

    # ------------------------------------------------------------------
    def run(self, fn, on_result=None, on_error=None,
            on_progress=None, on_finished=None) -> int:
        """
        Schedule `fn(job)` on the thread pool.

        Args:
            fn:           Callable receiving a Job handle.
            on_result:    slot(result)
            on_error:     slot(formatted_traceback_str)
            on_progress:  slot(percent:int, message:str)
            on_finished:  slot() — always called (even on error/cancel)

        Returns:
            job_id (int) for cancellation.
        """
        signals = _JobSignals()
        if on_result:
            signals.result.connect(on_result)
        if on_error:
            signals.error.connect(on_error)
        if on_progress:
            signals.progress.connect(on_progress)
        if on_finished:
            signals.finished.connect(on_finished)

        job_id = self._next_id
        self._next_id += 1
        self._active[job_id] = signals

        # Auto-cleanup when the job finishes
        signals.finished.connect(lambda jid=job_id: self._active.pop(jid, None))

        runnable = _JobRunnable(fn, signals)
        self._pool.start(runnable)
        return job_id

    # ------------------------------------------------------------------
    def cancel(self, job_id: int):
        """Request cooperative cancellation of a running job."""
        signals = self._active.get(job_id)
        if signals:
            signals.cancel_requested = True

    def cancel_all(self):
        for signals in self._active.values():
            signals.cancel_requested = True

    def wait_for_done(self, msecs: int = 3000) -> bool:
        return self._pool.waitForDone(msecs)
