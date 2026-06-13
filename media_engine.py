"""
Cantio - Media Engine  (v2, with frame throttling)
=======================================================
Architecture
------------
  VideoDecodeThread (QThread)
    └─ opens cv2.VideoCapture with buffer=1 (no frame queue in OpenCV)
    └─ decodes at ≤30 fps and emits a **numpy RGB array** (no QImage conversion)
    └─ _frame_pending flag: drops new frames while the previous one is being
       processed by the RenderEngine (back-pressure, prevents queue build-up)
    └─ frame_consumed() slot: clears _frame_pending so next frame can be sent

  MediaEngine (QObject, lives on main thread)
    └─ owns VideoDecodeThread
    └─ re-emits frame_ready(numpy_rgb_array) for RenderEngine.set_video_frame()
    └─ exposes frame_consumed() for back-pressure callback

Why numpy instead of QImage / QPixmap
--------------------------------------
Converting to QImage / QPixmap on the main thread is wasted work because
RenderWorker already converts numpy → QImage → QPixmap on the render thread.
Emitting the raw numpy array avoids one extra conversion on the main thread.

Usage
-----
    from media_engine import MediaEngine

    self.media_engine = MediaEngine(self)
    # Connect to RenderEngine (which also notifies back via set_video_source)
    self.media_engine.frame_ready.connect(self.render_engine.set_video_frame,
                                          Qt.ConnectionType.QueuedConnection)
    self.render_engine.set_video_source(self.media_engine.current_thread())

    self.media_engine.play("/path/to/background.mp4")
    self.media_engine.stop()   # call on close
"""
from __future__ import annotations

import time

from PyQt6.QtCore import (
    QObject, QThread, QMutex, QMutexLocker,
    pyqtSignal, pyqtSlot, Qt,
)

# ── Optional cv2 ──────────────────────────────────────────────────────────────

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    cv2    = None    # type: ignore[assignment]
    HAS_CV2 = False

_TARGET_FPS = 30


# ── Video decode thread ────────────────────────────────────────────────────────

class VideoDecodeThread(QThread):
    """
    Decodes video frames from a file in a background thread.

    Emits frame_ready(object) where the payload is a **numpy RGB array**.
    The _frame_pending flag provides back-pressure: the thread skips a frame
    whenever the previous one hasn't been consumed yet by the render engine.
    """

    frame_ready = pyqtSignal(object)   # numpy RGB array (h, w, 3) uint8

    def __init__(self, path: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._path          = path
        self._stopped       = False
        self._frame_pending = False
        self._mutex         = QMutex()

    # ── Stop API ──────────────────────────────────────────────────────────────

    def stop(self, wait_ms: int = 2000) -> None:
        with QMutexLocker(self._mutex):
            self._stopped = True
        self.requestInterruption()
        if not self.wait(wait_ms):
            self.terminate()

    # ── Back-pressure ─────────────────────────────────────────────────────────

    @pyqtSlot()
    def frame_consumed(self) -> None:
        """
        Called by RenderEngine after it has processed the previous frame.
        Clears the pending flag so the decode loop may emit the next frame.
        """
        self._frame_pending = False

    # ── Thread body ───────────────────────────────────────────────────────────

    def run(self) -> None:
        if not HAS_CV2 or cv2 is None:
            return

        cap = cv2.VideoCapture(self._path)
        if not cap.isOpened():
            return

        # Keep the OpenCV internal buffer at 1 frame so we always get the
        # freshest frame and don't accumulate a growing backlog.
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        fps      = min(cap.get(cv2.CAP_PROP_FPS) or float(_TARGET_FPS), _TARGET_FPS)
        interval = 1.0 / fps

        try:
            while True:
                with QMutexLocker(self._mutex):
                    if self._stopped:
                        break
                if self.isInterruptionRequested():
                    break

                t0 = time.monotonic()

                ok, frame = cap.read()
                if not ok:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue

                # ── Back-pressure: drop frame if render engine is still busy ──
                if self._frame_pending:
                    # Pace the loop even when dropping frames
                    elapsed = time.monotonic() - t0
                    sleep   = interval - elapsed
                    if sleep > 0:
                        time.sleep(sleep)
                    continue

                # ── Resize to 1920×1080 (render engine expects fixed size) ────
                fh, fw = frame.shape[:2]
                if fw != 1920 or fh != 1080:
                    frame = cv2.resize(
                        frame, (1920, 1080),
                        interpolation=cv2.INTER_LINEAR,
                    )

                # ── BGR → RGB ─────────────────────────────────────────────────
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Mark pending BEFORE emitting (avoid double-emit race)
                self._frame_pending = True
                self.frame_ready.emit(rgb)

                # ── Pace to target FPS ────────────────────────────────────────
                elapsed = time.monotonic() - t0
                sleep   = interval - elapsed
                if sleep > 0:
                    time.sleep(sleep)
        finally:
            cap.release()


# ── Media Engine ──────────────────────────────────────────────────────────────

class MediaEngine(QObject):
    """
    Manages a VideoDecodeThread and re-emits its numpy arrays.

    frame_ready(object) — numpy RGB array (1920×1080, uint8)
        Connect to RenderEngine.set_video_frame with QueuedConnection.
    """

    frame_ready = pyqtSignal(object)   # numpy RGB array

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: VideoDecodeThread | None = None

    # ── Playback control ──────────────────────────────────────────────────────

    def play(self, path: str) -> None:
        """Start (or restart) video decoding from *path*."""
        self.stop()
        if not HAS_CV2:
            return
        t = VideoDecodeThread(path)
        t.frame_ready.connect(self._on_frame, Qt.ConnectionType.QueuedConnection)
        t.finished.connect(self._on_thread_finished)
        self._thread = t
        t.start()

    def stop(self) -> None:
        """Stop decode thread immediately (non-blocking)."""
        t, self._thread = self._thread, None
        if t is not None and t.isRunning():
            t.stop()

    def is_active(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def current_thread(self) -> VideoDecodeThread | None:
        """Return the active decode thread (for RenderEngine back-pressure wiring)."""
        return self._thread

    # ── Back-pressure passthrough ─────────────────────────────────────────────

    def frame_consumed(self) -> None:
        """Forward frame_consumed to the active decode thread."""
        if self._thread is not None:
            self._thread.frame_consumed()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _on_frame(self, rgb_array) -> None:
        """Re-emit the numpy array (no conversion — happens on render thread)."""
        self.frame_ready.emit(rgb_array)

    def _on_thread_finished(self) -> None:
        sender = self.sender()
        if self._thread is sender:
            self._thread = None
