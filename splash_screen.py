"""
Cantio - Splash Screen
Shown at startup while loading.  Uses SplashScreen.png as full-bleed background
(falls back to GPSPLASH-cutout.png → GProICON.png if missing).
"""
from __future__ import annotations
import os

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QProgressBar, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation
from PyQt6.QtGui import QPixmap, QColor, QPainter, QLinearGradient

from translations import t

_BASE = os.path.dirname(__file__)


def _find_splash_image() -> str | None:
    """Return path to the best available splash image, or None."""
    for name in ("SplashScreen.png", "GPSPLASH-cutout.png"):
        p = os.path.join(_BASE, name)
        if os.path.exists(p):
            return p
    return None


class SplashScreen(QWidget):
    W, H = 900, 506          # 16:9

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.W, self.H)

        # Centre on primary screen
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            self.move(
                (geom.width()  - self.W) // 2,
                (geom.height() - self.H) // 2,
            )

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Background image label ────────────────────────────────────────────
        self.bg_label = QLabel()
        self.bg_label.setFixedSize(self.W, self.H)

        img_path = _find_splash_image()
        if img_path:
            pix = QPixmap(img_path)
        else:
            pix = QPixmap()

        if not pix.isNull():
            scaled = pix.scaled(
                self.W, self.H,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.bg_label.setPixmap(scaled)
        else:
            # No image found — paint a dark gradient background
            self.bg_label.setStyleSheet(
                "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                "stop:0 #181825, stop:1 #11111b); border-radius: 12px;"
            )

        # ── Transparent overlay (version + status + progress) ─────────────────
        overlay = QWidget(self.bg_label)
        overlay.setGeometry(0, 0, self.W, self.H)
        overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        overlay.setStyleSheet("background: transparent;")

        ov_layout = QVBoxLayout(overlay)
        ov_layout.setContentsMargins(40, 20, 40, 28)
        ov_layout.addStretch()

        # Version — bottom right
        version_row = QHBoxLayout()
        version_row.addStretch()
        self.version_label = QLabel("v1.5.0")
        self.version_label.setStyleSheet(
            "color: rgba(255,255,255,0.6); font-size: 12px; font-family: 'Segoe UI';"
            "background: transparent;"
        )
        version_row.addWidget(self.version_label)
        ov_layout.addLayout(version_row)

        # Status text
        self.status_label = QLabel(t("initializing_label"))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "color: rgba(255,255,255,0.85); font-size: 13px; font-family: 'Segoe UI';"
            "margin-bottom: 6px; background: transparent;"
        )
        ov_layout.addWidget(self.status_label)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setStyleSheet("""
            QProgressBar {
                background: rgba(255,255,255,0.15);
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4d9fff,
                    stop:1 #a0c8ff);
                border-radius: 2px;
            }
        """)
        ov_layout.addWidget(self.progress)

        root.addWidget(self.bg_label)

    # ── Fallback paintEvent (when no bg image) ────────────────────────────────

    def paintEvent(self, event):
        """Only used when no background image was loaded."""
        img_path = _find_splash_image()
        if img_path:
            return  # bg_label has an image — nothing extra to paint
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, 0, self.H)
        grad.setColorAt(0, QColor("#181825"))
        grad.setColorAt(1, QColor("#11111b"))
        p.setBrush(grad)
        p.setPen(QColor("#2a2a3e"))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_message(self, msg: str):
        self.status_label.setText(msg)
        QApplication.processEvents()

    def set_progress(self, val: int):
        self.progress.setValue(val)
        QApplication.processEvents()

    # Backward-compatible wrapper used by main.py
    def set_status(self, text: str, progress: int):
        self.set_message(text)
        self.set_progress(progress)

    def fade_out_and_close(self, callback=None):
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(400)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        if callback:
            self._anim.finished.connect(lambda: callback(self))
        self._anim.finished.connect(self.close)
        self._anim.start()

    def finish(self):
        self.fade_out_and_close()


# ── run_splash helper (called from main.py) ───────────────────────────────────

def run_splash(on_done_callback):
    """
    Show splash, animate through startup steps, then call on_done_callback(splash).
    The callback receives the SplashScreen instance so it can call splash.finish()
    when the app is fully initialised.
    """
    splash = SplashScreen()
    splash.show()
    QApplication.processEvents()

    steps = [
        (t("loading_db"),       15),
        (t("checking_profile"), 45),
        (t("initializing"),     75),
    ]

    step_idx = [0]
    timings = [450, 600, 550]

    def next_step():
        i = step_idx[0]
        if i < len(steps):
            splash.set_status(steps[i][0], steps[i][1])
            step_idx[0] += 1
            QTimer.singleShot(timings[i], next_step)
        else:
            on_done_callback(splash)

    QTimer.singleShot(200, next_step)
    return splash
