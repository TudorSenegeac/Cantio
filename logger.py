"""
Cantio - Structured File Logger
Writes daily rotating log files to ~/Cantio/logs/
Keeps the last 7 log files.  Falls back silently on any I/O error.
"""
import logging
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.expanduser("~"), "Cantio", "logs")

_root_logger: logging.Logger | None = None


def setup_logger() -> logging.Logger:
    """
    Create (or return) the application root logger.
    Calling this more than once is safe — handlers are not duplicated.
    """
    global _root_logger
    logger = logging.getLogger("Cantio")

    if logger.handlers:          # already initialised
        _root_logger = logger
        return logger

    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # ── File handler (DEBUG+) ──────────────────────────────────────────────────
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        log_file = os.path.join(
            LOG_DIR,
            f"cantio_{datetime.now().strftime('%Y%m%d')}.log",
        )
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        _cleanup_old_logs()
    except Exception as _e:
        pass   # never crash the app over a missing log directory

    # ── Console handler (WARNING+) ─────────────────────────────────────────────
    try:
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    except Exception:
        pass

    _root_logger = logger
    return logger


def _cleanup_old_logs():
    """Delete log files older than the most-recent 7."""
    try:
        logs = sorted(
            f for f in os.listdir(LOG_DIR) if f.endswith(".log")
        )
        while len(logs) > 7:
            os.remove(os.path.join(LOG_DIR, logs.pop(0)))
    except Exception:
        pass


def get_logger(name: str = "Cantio") -> logging.Logger:
    """Return a child logger.  setup_logger() need not be called first."""
    return logging.getLogger(name)
