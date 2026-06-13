"""
Cantio - Async Database Thread
Provides non-blocking, background-thread execution of blocking DB operations
via QThreadPool (no dedicated thread needed for simple fire-and-forget calls).

Usage
-----
    from db_thread import async_db
    import database as db

    # Fire-and-forget: results go to callback on the main thread
    async_db.run(db.get_songs, callback=self._on_songs_loaded)

    # With arguments and error handler
    async_db.run(db.search_songs, query,
                 callback=self._on_results,
                 on_error=self._on_db_error)

    # Blocking (synchronous) — keep on main thread for writes
    db.add_song(title, content, category)

Notes
-----
- Callbacks are connected via Qt signals so they always fire on the main
  (GUI) thread — safe to update widgets directly.
- Returned `_WorkerSignals` object can be ignored; Qt owns the lifetime.
- Max 2 DB threads by default (SQLite supports concurrent reads).
"""
from __future__ import annotations

import traceback
from typing import Any, Callable, Optional

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot


# ── Worker signals (must live on QObject so signals work) ────────────────────

class _WorkerSignals(QObject):
    """Signals emitted by _Task back to the main thread."""
    result = pyqtSignal(object)   # successful return value
    error  = pyqtSignal(object)   # Exception instance


# ── Runnable task ─────────────────────────────────────────────────────────────

class _Task(QRunnable):
    """
    A single unit of work dispatched to QThreadPool.
    Calls fn(*args, **kwargs) in a worker thread, then emits result or error
    on the main thread via Qt signals.
    """

    def __init__(self,
                 fn:      Callable,
                 args:    tuple,
                 kwargs:  dict,
                 signals: _WorkerSignals):
        super().__init__()
        self._fn      = fn
        self._args    = args
        self._kwargs  = kwargs
        self._signals = signals
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
            self._signals.result.emit(result)
        except Exception as exc:
            traceback.print_exc()
            self._signals.error.emit(exc)


# ── Public API ────────────────────────────────────────────────────────────────

class AsyncDB:
    """
    Thin convenience wrapper around the global QThreadPool for async DB calls.

    Parameters
    ----------
    max_threads : int
        Maximum concurrent worker threads.  2 is a safe default for SQLite
        (one reader, one writer queued behind it via SQLite's WAL mode).
    """

    def __init__(self, max_threads: int = 2) -> None:
        self._pool = QThreadPool.globalInstance()
        # Don't lower the global max if it is already higher
        current = self._pool.maxThreadCount()
        if current < max_threads:
            self._pool.setMaxThreadCount(max_threads)

    def run(self,
            fn: Callable,
            /,
            *args: Any,
            callback:  Optional[Callable] = None,
            on_error:  Optional[Callable] = None,
            **kwargs: Any) -> _WorkerSignals:
        """
        Execute *fn* in a background thread.

        Parameters
        ----------
        fn       : callable to run (e.g. db.get_songs)
        *args    : positional arguments forwarded to fn
        callback : called on the main thread with fn's return value
        on_error : called on the main thread with the Exception on failure
        **kwargs : keyword arguments forwarded to fn

        Returns
        -------
        _WorkerSignals
            You can connect additional slots to .result / .error if needed.
            The task keeps a reference internally; safe to discard.
        """
        signals = _WorkerSignals()
        if callback is not None:
            signals.result.connect(callback)
        if on_error is not None:
            signals.error.connect(on_error)

        task = _Task(fn, args, kwargs, signals)
        self._pool.start(task)

        # Keep the signals object alive until the task finishes.
        # QRunnable.setAutoDelete(True) frees the task; the signals object is
        # freed when no more slots are connected.  Store it on the task (which
        # the pool owns during execution) so it outlives the local frame.
        task._signals = signals   # type: ignore[attr-defined]  (already set above)

        return signals

    @property
    def active_thread_count(self) -> int:
        return self._pool.activeThreadCount()

    def wait_for_done(self, timeout_ms: int = 5000) -> None:
        """Block until all queued tasks finish (useful in tests / shutdown)."""
        self._pool.waitForDone(timeout_ms)


# ── Module-level singleton ─────────────────────────────────────────────────────

#: Global AsyncDB instance — import and use directly.
async_db = AsyncDB()
