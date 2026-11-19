"""
Cantio - Live State
Single shared state object observed by DisplayWindow(s) and PreviewWidget.
Observer pattern: call add_observer(callback) to subscribe; notify() fires all callbacks.
"""
import time
from PyQt6.QtCore import QTimer


class LiveState:
    def __init__(self):
        self.current_text   = ""
        self.settings       = {}
        self.bg_pixmap      = None   # QPixmap or None
        self.bg_video_frame = None   # QImage or None (future use)
        self.ticker_text    = ""
        self.ticker_active  = False
        self.ticker_x       = 0.0
        self.ticker_speed   = 2.5
        self.show_clock     = False
        self.clock_color    = "#ffffff"
        self.clock_fmt      = "HH:MM:SS"
        self.show_timer     = False
        self.timer_seconds  = 0
        self.timer_start    = 0.0
        self.timer_running  = False
        self.logo_pixmap    = None   # QPixmap or None
        self.logo_active    = False
        self.projector_off  = False
        self.opacity        = 1.0
        self._observers     = []

        # Internal ticker animation timer (16 ms ≈ 60 fps)
        self._ticker_timer = QTimer()
        self._ticker_timer.setInterval(16)
        self._ticker_timer.timeout.connect(self._tick_ticker)

        # Clock refresh timer (500 ms)
        self._clock_timer = QTimer()
        self._clock_timer.setInterval(500)
        self._clock_timer.timeout.connect(self.notify)

        # Countdown timer (1 s)
        self._countdown_timer = QTimer()
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick_countdown)

    # ── Observer ──────────────────────────────────────────────────────────────

    def add_observer(self, callback):
        if callback not in self._observers:
            self._observers.append(callback)

    def remove_observer(self, callback):
        if callback in self._observers:
            self._observers.remove(callback)

    def notify(self):
        for cb in list(self._observers):
            try:
                cb()
            except Exception:
                pass

    # ── Setters ───────────────────────────────────────────────────────────────

    def set_text(self, text):
        self.current_text = text
        self.notify()

    def set_settings(self, s: dict):
        self.settings = s
        self.notify()

    def set_bg(self, pixmap=None, video_frame=None):
        self.bg_pixmap = pixmap
        self.bg_video_frame = video_frame
        self.notify()

    def set_ticker(self, text: str, active: bool, speed: float = 2.5, x: float = 0.0):
        self.ticker_text   = text
        self.ticker_active = active and bool(text)
        self.ticker_speed  = max(0.5, speed)
        if not x:
            self.ticker_x = 0.0   # will be initialised on first paint
        if self.ticker_active:
            if not self._ticker_timer.isActive():
                self._ticker_timer.start()
        else:
            self._ticker_timer.stop()
        self.notify()

    def set_clock(self, visible: bool, color: str = "#ffffff", fmt: str = "HH:MM:SS"):
        self.show_clock  = visible
        self.clock_color = color
        self.clock_fmt   = fmt
        if visible:
            if not self._clock_timer.isActive():
                self._clock_timer.start()
        else:
            self._clock_timer.stop()
        self.notify()

    def set_timer(self, seconds: int, running: bool, start: float = 0.0):
        self.timer_seconds = int(seconds)
        self.timer_running = running
        self.timer_start   = start or time.monotonic()
        if running:
            if not self._countdown_timer.isActive():
                self._countdown_timer.start()
        else:
            self._countdown_timer.stop()
        self.notify()

    def set_logo(self, pixmap, active: bool):
        self.logo_pixmap = pixmap
        self.logo_active = active
        self.notify()

    def set_projector_off(self, v: bool):
        self.projector_off = v
        self.notify()

    def set_opacity(self, v: float):
        self.opacity = float(v)
        self.notify()

    # ── Internal timers ───────────────────────────────────────────────────────

    def _tick_ticker(self):
        self.ticker_x -= self.ticker_speed
        self.notify()

    def _tick_countdown(self):
        if self.timer_seconds > 0:
            self.timer_seconds -= 1
        if self.timer_seconds <= 0:
            self._countdown_timer.stop()
        self.notify()

    def stop_all_timers(self):
        self._ticker_timer.stop()
        self._clock_timer.stop()
        self._countdown_timer.stop()


# ── Module-level singleton ────────────────────────────────────────────────────

_state = LiveState()


def get_state() -> LiveState:
    return _state


def reset_state():
    global _state
    _state.stop_all_timers()
    _state = LiveState()
