"""
Cantio - Main Entry Point
Church lyrics display software.
"""
import sys
import os
import signal

# ── UTF-8 stdout/stderr fix for Windows consoles (cp1250/cp1252) ──────────────
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# Suppress OpenCV camera-detection noise BEFORE any cv2 import
os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")
os.environ.setdefault("OPENCV_VIDEOIO_DEBUG", "0")

from paths import get_data_dir
app_data = get_data_dir()
os.makedirs(app_data, exist_ok=True)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap

from logger import setup_logger
import database as db
import profile_manager as pm
from translations import t, set_language

# Initialise structured logging as early as possible
_logger = setup_logger()
_logger.info("Cantio pornit (v1.5.2)")


def _global_exception_handler(exc_type, exc_value, exc_tb):
    """Log unhandled exceptions and show a user-friendly dialog."""
    import traceback
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _logger.critical("Excepție necaptată:\n%s", tb_str)
    try:
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setWindowTitle("Cantio — Eroare")
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText(
            "Aplicația a întâmpinat o eroare neașteptată și trebuie repornită.\n\n"
            f"{exc_type.__name__}: {exc_value}"
        )
        from logger import LOG_DIR
        import datetime
        log_file = os.path.join(LOG_DIR, f"cantio_{datetime.date.today().strftime('%Y%m%d')}.log")
        msg.setInformativeText(f"Detaliile erorii au fost salvate în:\n{log_file}")
        msg.exec()
    except Exception:
        pass


sys.excepthook = _global_exception_handler


def _set_app_icon(app: QApplication):
    base = os.path.dirname(__file__)
    # Prefer new branded icon, fall back to legacy name
    for name in ("GProICON.png", "Cantio.ico", "Cantio_icon.png"):
        p = os.path.join(base, name)
        if os.path.exists(p):
            app.setWindowIcon(QIcon(p))
            break


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Cantio")
    app.setOrganizationName("Cantio")
    app.setApplicationVersion("1.5.2")

    # Prevent Qt from quitting automatically when the splash (or any dialog)
    # closes before the main window is visible — fixes the race condition where
    # the app exits immediately if the user clicks "Open Profile" after the
    # splash has already disappeared.
    app.setQuitOnLastWindowClosed(False)

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    _set_app_icon(app)

    # Load language preference BEFORE any widgets are created (reads Default profile)
    try:
        db.set_active_profile("Default")
        _lang = db.get_settings().get("language", "ro")
        set_language(_lang)
    except Exception:
        pass  # stay with default "ro" if settings unreadable

    from splash_screen import run_splash

    _window_holder = []
    _dlg_holder = [None]   # mutable ref so the close-splash timer can reach the dialog

    def _launch(splash):
        # If we were relaunched by a profile switch, open that profile directly
        # (skip the selection dialog).
        _pending = None
        try:
            _flag = os.path.join(os.path.expanduser("~"), "Cantio", ".pending_profile")
            if os.path.exists(_flag):
                with open(_flag, encoding="utf-8") as f:
                    _pending = f.read().strip()
                os.remove(_flag)
        except Exception:
            _pending = None

        if _pending:
            profile = _pending
        else:
            # Profile selection (quick — splash still visible)
            dlg = pm.ProfileSelectDialog()
            _dlg_holder[0] = dlg   # expose to the timer below
            dlg.exec()
            profile = dlg.selected_profile or "Default"

        pm.create_profile(profile)
        db.set_active_profile(profile)

        # Detect if old monolithic DB exists → migration will run in init_db()
        # Verify DB integrity; auto-repair if corrupted before any schema work
        splash.set_status(t("checking_profile"), 50)
        db.check_and_repair_db()

        db.init_db()

        # Re-apply language for the selected profile (may differ from Default)
        try:
            _profile_lang = db.get_settings().get("language", "ro")
            set_language(_profile_lang)
        except Exception:
            pass

        splash.set_status(t("starting_ui"), 95)

        from control_window import ControlWindow
        window = ControlWindow(profile_name=profile)
        window.show()
        _window_holder.append(window)

        # Quit the application only when the main window is actually closed
        # (safe to call after setQuitOnLastWindowClosed(False))
        window.destroyed.connect(app.quit)

        splash.set_status(t("ready"), 100)
        # Short delay so user sees "Gata!" before splash disappears
        QTimer.singleShot(300, splash.finish)

    # Force-quit on SIGTERM (e.g. task-kill, system shutdown)
    signal.signal(signal.SIGTERM, lambda s, f: app.quit())

    splash = run_splash(_launch)

    # Safety net: after the full animation (~2800 ms) force-close the splash and
    # bring the profile-selection dialog to the front in case it opened behind it.
    def _ensure_splash_closed():
        splash.close()
        dlg = _dlg_holder[0]
        if dlg is not None and dlg.isVisible():
            dlg.raise_()
            dlg.activateWindow()

    QTimer.singleShot(2800, _ensure_splash_closed)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
