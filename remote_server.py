"""
Cantio - Web Remote Control Server  (v2 — Flask-SocketIO)
=========================================================
Flask + Socket.IO backend running in a daemon thread.
Mobile-first dark UI accessible via LAN browser — no app install needed.

Architecture
------------
  Qt main thread  ──write──►  _state dict   ──read──►  /api/state  (REST)
  Qt main thread  ──write──►  _state dict   ──push──►  socketio.emit('state', …)
  Browser         ──emit───►  'cmd' event   ──write──►  _command_queue
  Qt QTimer (300ms)──poll──►  _command_queue ──calls──►  ControlWindow slots
"""

import threading
import socket
import queue
import io
import base64
import json
import logging
from typing import Optional

log = logging.getLogger(__name__)

# ── Shared state (Qt writes, Flask reads) ─────────────────────────────────────

_state: dict = {
    "current_text":       "",
    "current_title":      "",
    "slide_index":        0,
    "slide_count":        0,
    "is_live":            False,
    "is_frozen":          False,
    "ticker":             "",
    "countdown_remaining": 0,
    "service_items":      [],   # [{title, slide_count}, …]
    "service_index":      -1,
    "song_list":          [],   # [{id, title}, …]
    "slides":             [],   # [{idx, text, label}, …]
    "display_open":       False,
    "current_song":       None, # {id, title, author}
}

_command_queue: queue.Queue = queue.Queue()
_server_thread: Optional[threading.Thread] = None
_server_port: int = 5050
_running = False
_control = None   # reference to ControlWindow (set by start_server)

# Flask app + SocketIO — created once
_app     = None
_socketio = None


# ── State helpers ─────────────────────────────────────────────────────────────

def update_state(**kwargs):
    """Called from the Qt main thread to push new state."""
    _state.update(kwargs)


def get_port() -> int:
    return _server_port


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_url() -> str:
    return f"http://{get_local_ip()}:{_server_port}"


def pop_command() -> Optional[dict]:
    """Called from Qt QTimer to drain the command queue (one call per tick)."""
    try:
        return _command_queue.get_nowait()
    except queue.Empty:
        return None


def is_running() -> bool:
    return _running and _server_thread is not None and _server_thread.is_alive()


def notify_state_change():
    """
    Called from the Qt main thread after any action that changes display state.
    Broadcasts the current _state to all connected WebSocket clients.
    """
    if not _running or _socketio is None:
        return
    try:
        _socketio.emit("state", dict(_state))
    except Exception as e:
        log.debug("[Remote] broadcast error: %s", e)


def generate_qr(url: str) -> str:
    """Return base-64 PNG of a QR code for *url*, or empty string on error."""
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=6, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="white", back_color="#1e1e2e")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    except Exception:
        return ""


# ── Flask / SocketIO app factory ──────────────────────────────────────────────

def _build_app():
    global _app, _socketio
    try:
        from flask import Flask, render_template_string, jsonify, request, Response
        from flask_socketio import SocketIO, emit as sio_emit
    except ImportError:
        return None, None

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "cantio_remote_2025"
    app.logger.setLevel(logging.ERROR)

    sio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode="threading",
        logger=False,
        engineio_logger=False,
    )

    # ── REST endpoints ──────────────────────────────────────────────────────

    @app.route("/")
    def index():
        return render_template_string(REMOTE_HTML)

    @app.route("/api/state")
    def api_state():
        return Response(
            json.dumps(dict(_state), ensure_ascii=False),
            mimetype="application/json",
        )

    @app.route("/api/songs")
    def api_songs():
        try:
            import database as db
            songs = db.search_songs_fast("") or []
            return Response(
                json.dumps([
                    {"id": s["id"], "title": s["title"],
                     "author": s.get("author", ""),
                     "category": s.get("category", "")}
                    for s in songs[:200]
                ], ensure_ascii=False),
                mimetype="application/json",
            )
        except Exception as e:
            return Response(json.dumps({"error": str(e)}), mimetype="application/json")

    @app.route("/api/songs/search/<path:query>")
    def api_songs_search(query):
        try:
            import database as db
            songs = db.search_songs_fast(query) or []
            return Response(
                json.dumps([
                    {"id": s["id"], "title": s["title"],
                     "author": s.get("author", "")}
                    for s in songs[:50]
                ], ensure_ascii=False),
                mimetype="application/json",
            )
        except Exception as e:
            return Response(json.dumps({"error": str(e)}), mimetype="application/json")

    @app.route("/api/song/<int:song_id>")
    def api_song(song_id):
        try:
            import database as db
            song = db.get_song(song_id)
            if not song:
                return Response(json.dumps({"error": "Not found"}),
                                mimetype="application/json", status=404)
            slides_raw = song.get("slides", [])
            return Response(
                json.dumps({
                    "id":     song["id"],
                    "title":  song["title"],
                    "author": song.get("author", ""),
                    "slides": [
                        s.get("text", s) if isinstance(s, dict) else str(s)
                        for s in slides_raw
                    ],
                }, ensure_ascii=False),
                mimetype="application/json",
            )
        except Exception as e:
            return Response(json.dumps({"error": str(e)}), mimetype="application/json")

    # ── SocketIO events ─────────────────────────────────────────────────────

    @sio.on("connect")
    def on_connect():
        sio_emit("state", dict(_state))
        log.debug("[Remote] client connected")

    @sio.on("disconnect")
    def on_disconnect():
        log.debug("[Remote] client disconnected")

    @sio.on("cmd")
    def on_command(data):
        """
        Commands received from the browser are queued so the Qt main-thread
        QTimer can safely execute them (no cross-thread Qt calls).
        """
        if not isinstance(data, dict):
            return
        cmd = data.get("cmd", "")
        if cmd:
            # Map new command names → old action names for backward compat
            _CMD_MAP = {
                "go_live":             "go_live",
                "black_screen":        "black",
                "clear_text":          "clear_text",
                "next_slide":          "next",
                "prev_slide":          "prev",
                "select_song":         "load_song",
                "select_service_item": "service_select",
                "open_display":        "open_display",
                "close_display":       "close_display",
                "freeze":              "freeze",
                "unfreeze":            "unfreeze",
                "ticker":              "ticker",
                "hide_ticker":         "hide_ticker",
            }
            action = _CMD_MAP.get(cmd, cmd)
            payload = dict(data)
            payload["action"] = action
            # song_id alias
            if "song_id" in data:
                payload["song_id"] = data["song_id"]
            # service item index
            if "idx" in data:
                payload["index"] = data["idx"]
            _command_queue.put(payload)

    _app = app
    _socketio = sio
    return app, sio


# ── Server lifecycle ──────────────────────────────────────────────────────────

def start_server(control_window=None, port: int = 5050):
    """
    Start the Flask-SocketIO server in a daemon thread.

    Parameters
    ----------
    control_window : ControlWindow | None
        Reference stored so REST endpoints can read live state.
    port : int
        TCP port to listen on (default 5050).

    Returns
    -------
    tuple[str, str]  (url, qr_base64_png)
        url           — e.g. "http://192.168.1.5:5050"
        qr_base64_png — base-64 PNG data, or "" if qrcode not installed.
    bool  (if Flask missing)
        False when Flask is not installed.
    """
    global _server_thread, _server_port, _running, _control

    if _running:
        return get_url(), generate_qr(get_url())

    _control = control_window

    app, sio = _build_app()
    if app is None or sio is None:
        return False

    _server_port = port
    _running = True

    def _run():
        import logging as _log
        _log.getLogger("werkzeug").setLevel(_log.ERROR)
        _log.getLogger("engineio").setLevel(_log.ERROR)
        _log.getLogger("socketio").setLevel(_log.ERROR)
        sio.run(
            app,
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False,
            log_output=False,
            allow_unsafe_werkzeug=True,
        )

    _server_thread = threading.Thread(target=_run, daemon=True, name="CantioRemote")
    _server_thread.start()

    url = get_url()
    qr  = generate_qr(url)
    log.info("[Remote] server started: %s", url)
    return url, qr


def stop_server():
    global _running
    _running = False
    log.info("[Remote] server stopped")


# ── HTML / CSS / JS of the Remote Web App ────────────────────────────────────

REMOTE_HTML = r"""<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport"
    content="width=device-width, initial-scale=1.0,
    maximum-scale=1.0, user-scalable=no">
<title>Cantio Remote</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
<style>
* { box-sizing:border-box; margin:0; padding:0; }
:root {
    --bg: #11111b;
    --surface: #1e1e2e;
    --surface2: #313244;
    --text: #cdd6f4;
    --subtext: #6c7086;
    --accent: #cba6f7;
    --green: #a6e3a1;
    --red: #f38ba8;
    --yellow: #f9e2af;
    --blue: #89b4fa;
}
body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', Arial, sans-serif;
    height: 100dvh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}
.header {
    background: var(--surface);
    padding: 10px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--surface2);
    flex-shrink: 0;
}
.header h1 { font-size: 18px; color: var(--accent); font-weight: 700; }
.status-dot {
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--red); display: inline-block; margin-right: 6px;
}
.status-dot.live { background: var(--green); animation: pulse 1s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
.nav-tabs {
    display: flex; background: var(--surface);
    border-bottom: 1px solid var(--surface2);
    flex-shrink: 0; overflow-x: auto;
}
.nav-tab {
    flex: 1; min-width: 60px; padding: 10px 8px;
    text-align: center; font-size: 11px; color: var(--subtext);
    cursor: pointer; border: none; background: none;
    border-bottom: 2px solid transparent; transition: all 0.2s; white-space: nowrap;
}
.nav-tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.nav-tab:hover { color: var(--text); background: var(--surface2); }
.content { flex: 1; overflow-y: auto; overflow-x: hidden; -webkit-overflow-scrolling: touch; }
.tab-content { display: none; padding: 12px; }
.tab-content.active { display: block; }
.live-preview {
    background: #000; border-radius: 8px;
    aspect-ratio: 16/9; display: flex;
    align-items: center; justify-content: center;
    margin-bottom: 12px; border: 2px solid var(--surface2);
    position: relative; overflow: hidden;
}
.live-preview.active { border-color: var(--green); }
.live-text {
    color: white; font-size: clamp(12px, 3vw, 24px);
    text-align: center; padding: 16px; font-weight: bold;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.8); line-height: 1.4;
}
.live-badge {
    position: absolute; top: 8px; right: 8px;
    background: var(--green); color: #1e1e2e;
    font-size: 10px; font-weight: bold;
    padding: 2px 8px; border-radius: 10px;
}
.ctrl-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
.ctrl-btn {
    padding: 14px 8px; border: none; border-radius: 8px;
    font-size: 14px; font-weight: bold; cursor: pointer;
    transition: all 0.15s; display: flex; flex-direction: column;
    align-items: center; gap: 4px;
}
.ctrl-btn:active { transform: scale(0.95); opacity: 0.8; }
.btn-live { background: var(--green); color: #1e1e2e; grid-column: 1/-1; font-size: 18px; padding: 18px; }
.btn-black { background: #181825; color: var(--red); border: 1px solid var(--red); }
.btn-clear { background: var(--surface2); color: var(--text); }
.btn-freeze { background: var(--surface2); color: var(--blue); }
.btn-freeze.active { background: rgba(137,180,250,0.2); border: 1px solid var(--blue); }
.btn-display { background: var(--surface2); color: var(--accent); }
.btn-display.active { background: rgba(203,166,247,0.2); border: 1px solid var(--accent); }
.nav-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
.nav-btn {
    padding: 16px; border: 1px solid var(--surface2);
    border-radius: 8px; background: var(--surface);
    color: var(--text); font-size: 16px; cursor: pointer;
    text-align: center; transition: all 0.15s;
}
.nav-btn:active { background: var(--surface2); transform: scale(0.95); }
.slides-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.slide-thumb {
    background: #000; border-radius: 6px; aspect-ratio: 16/9;
    display: flex; align-items: center; justify-content: center;
    padding: 8px; cursor: pointer; border: 2px solid var(--surface2);
    transition: all 0.15s; position: relative; overflow: hidden;
}
.slide-thumb:active { transform: scale(0.95); }
.slide-thumb.current { border-color: var(--accent); }
.slide-thumb.live { border-color: var(--green); }
.slide-thumb-text {
    font-size: 9px; color: white; text-align: center; line-height: 1.3;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.9);
    display: -webkit-box; -webkit-line-clamp: 4;
    -webkit-box-orient: vertical; overflow: hidden;
}
.slide-num { position: absolute; top: 3px; left: 4px; font-size: 8px; color: rgba(255,255,255,0.5); }
.service-item {
    background: var(--surface); border-radius: 8px;
    padding: 12px 14px; margin-bottom: 8px; cursor: pointer;
    border: 1px solid var(--surface2);
    display: flex; align-items: center; gap: 10px; transition: all 0.15s;
}
.service-item:active { background: var(--surface2); }
.service-item.active { border-color: var(--accent); background: rgba(203,166,247,0.1); }
.service-icon { font-size: 20px; flex-shrink: 0; }
.service-info { flex: 1; min-width: 0; }
.service-title { font-weight: bold; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.service-sub { font-size: 11px; color: var(--subtext); }
.search-bar { display: flex; gap: 8px; margin-bottom: 12px; }
.search-input {
    flex: 1; background: var(--surface); border: 1px solid var(--surface2);
    border-radius: 8px; padding: 10px 14px; color: var(--text); font-size: 14px; outline: none;
}
.search-input:focus { border-color: var(--accent); }
.search-btn { background: var(--accent); color: #1e1e2e; border: none; border-radius: 8px; padding: 10px 14px; font-weight: bold; cursor: pointer; }
.song-item {
    background: var(--surface); border-radius: 8px;
    padding: 12px 14px; margin-bottom: 6px; cursor: pointer;
    border: 1px solid var(--surface2); transition: all 0.15s;
}
.song-item:active { background: var(--surface2); }
.song-title { font-weight: bold; font-size: 13px; }
.song-author { font-size: 11px; color: var(--subtext); margin-top: 2px; }
.ticker-row { display: flex; gap: 8px; margin-bottom: 8px; }
.ticker-input {
    flex: 1; background: var(--surface); border: 1px solid var(--surface2);
    border-radius: 8px; padding: 10px 12px; color: var(--text); font-size: 13px; outline: none;
}
.ticker-send { background: var(--yellow); color: #1e1e2e; border: none; border-radius: 8px; padding: 10px 14px; font-weight: bold; cursor: pointer; }
.ticker-stop { background: var(--surface2); color: var(--red); border: 1px solid var(--red); border-radius: 8px; padding: 10px 14px; cursor: pointer; }
.section-title {
    font-size: 11px; font-weight: bold; color: var(--subtext);
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; margin-top: 12px;
}
.section-title:first-child { margin-top: 0; }
.toast {
    position: fixed; bottom: 20px; left: 50%;
    transform: translateX(-50%) translateY(80px);
    background: var(--surface2); color: var(--text);
    padding: 10px 20px; border-radius: 20px; font-size: 13px;
    transition: transform 0.3s; z-index: 1000;
    white-space: nowrap; pointer-events: none;
}
.toast.show { transform: translateX(-50%) translateY(0); }
</style>
</head>
<body>

<div class="header">
    <h1>🎵 Cantio</h1>
    <div>
        <span class="status-dot" id="statusDot"></span>
        <span id="statusText" style="font-size:12px;color:var(--subtext)">Conectare...</span>
    </div>
</div>

<div class="nav-tabs">
    <button class="nav-tab active" onclick="switchTab('control')">🎛 Control</button>
    <button class="nav-tab"        onclick="switchTab('slides')">🖼 Slide-uri</button>
    <button class="nav-tab"        onclick="switchTab('service')">📋 Serviciu</button>
    <button class="nav-tab"        onclick="switchTab('songs')">🎵 Cântări</button>
    <button class="nav-tab"        onclick="switchTab('extras')">⚙ Extra</button>
</div>

<div class="content">

<!-- CONTROL -->
<div id="tab-control" class="tab-content active">
    <div class="live-preview" id="livePreview">
        <div class="live-text" id="liveText">Niciun slide activ</div>
        <div class="live-badge" id="liveBadge" style="display:none">LIVE</div>
    </div>
    <div class="ctrl-grid">
        <button class="ctrl-btn btn-live"    onclick="cmd('go_live')">▶ GO LIVE</button>
        <button class="ctrl-btn btn-black"   onclick="cmd('black_screen')">⬛<span>Ecran Negru</span></button>
        <button class="ctrl-btn btn-clear"   onclick="cmd('clear_text')">⬜<span>Clear Text</span></button>
        <button class="ctrl-btn btn-freeze"  id="freezeBtn" onclick="toggleFreeze()">❄<span>Freeze</span></button>
        <button class="ctrl-btn btn-display" id="displayBtn" onclick="toggleDisplay()">📺<span id="displayBtnText">Display OFF</span></button>
    </div>
    <div class="nav-row">
        <button class="nav-btn" onclick="cmd('prev_slide')">◄ Anterior</button>
        <button class="nav-btn" onclick="cmd('next_slide')">Următor ►</button>
    </div>
    <div class="section-title">Cântarea curentă</div>
    <div id="currentSongInfo" style="font-size:13px;color:var(--subtext);margin-bottom:8px;">—</div>
</div>

<!-- SLIDES -->
<div id="tab-slides" class="tab-content">
    <div id="slidesGrid" class="slides-grid">
        <div style="color:var(--subtext);text-align:center;grid-column:1/-1;padding:20px;">
            Selectează o cântare
        </div>
    </div>
</div>

<!-- SERVICIU -->
<div id="tab-service" class="tab-content">
    <div id="serviceList">
        <div style="color:var(--subtext);text-align:center;padding:20px;">Serviciul e gol</div>
    </div>
</div>

<!-- CÂNTĂRI -->
<div id="tab-songs" class="tab-content">
    <div class="search-bar">
        <input type="text" class="search-input" id="songSearch"
               placeholder="Caută cântări..."
               onkeydown="if(event.key==='Enter')searchSongs()">
        <button class="search-btn" onclick="searchSongs()">🔍</button>
    </div>
    <div id="songsList"></div>
</div>

<!-- EXTRA -->
<div id="tab-extras" class="tab-content">
    <div class="section-title">Ticker / Alertă</div>
    <div class="ticker-row">
        <input type="text" class="ticker-input" id="tickerText" placeholder="Text alertă...">
        <button class="ticker-send" onclick="sendTicker()">Trimite</button>
        <button class="ticker-stop" onclick="cmd('hide_ticker')">Stop</button>
    </div>
    <div class="section-title">Informații Conexiune</div>
    <div style="background:var(--surface);border-radius:8px;padding:12px;font-size:12px;color:var(--subtext)">
        <div>Server: <span id="serverInfo" style="color:var(--text)">—</span></div>
    </div>
</div>

</div><!-- .content -->

<div class="toast" id="toast"></div>

<script>
const socket = io()
let state = {}
let frozen = false
let displayOpen = false

socket.on('connect', () => {
    updateStatus(true)
    document.getElementById('serverInfo').textContent = window.location.host
    showToast('Conectat la Cantio!')
})
socket.on('disconnect', () => updateStatus(false))
socket.on('state', (data) => { state = data; updateUI() })
socket.on('error', (data) => showToast('❌ ' + data.msg, true))

function updateStatus(connected) {
    document.getElementById('statusDot').className = 'status-dot' + (connected ? ' live' : '')
    document.getElementById('statusText').textContent = connected ? 'Conectat' : 'Deconectat'
}

function updateUI() {
    // Live preview
    const text = state.live_text || state.current_text || ''
    document.getElementById('liveText').textContent = text || 'Niciun slide activ'
    const isLive = (state.is_live && text)
    document.getElementById('liveBadge').style.display = isLive ? 'block' : 'none'
    document.getElementById('livePreview').className = 'live-preview' + (isLive ? ' active' : '')

    // Song info
    const si = document.getElementById('currentSongInfo')
    if (state.current_song) {
        si.textContent = state.current_song.title +
            (state.current_song.author ? ' — ' + state.current_song.author : '')
    } else if (state.current_title) {
        si.textContent = state.current_title
    } else {
        si.textContent = '—'
    }

    // Display button
    displayOpen = state.display_open || false
    const dispBtn = document.getElementById('displayBtn')
    const dispTxt = document.getElementById('displayBtnText')
    if (displayOpen) {
        dispBtn.style.borderColor = 'var(--accent)'
        dispBtn.style.background  = 'rgba(203,166,247,0.2)'
        dispTxt.textContent = 'Display ON'
    } else {
        dispBtn.style.borderColor = ''
        dispBtn.style.background  = ''
        dispTxt.textContent = 'Display OFF'
    }

    updateSlidesGrid()
    updateServiceList()
}

function updateSlidesGrid() {
    const grid = document.getElementById('slidesGrid')
    const slides = state.slides || []
    const curIdx = state.slide_index || 0
    if (!slides.length) {
        grid.innerHTML = '<div style="color:var(--subtext);text-align:center;grid-column:1/-1;padding:20px;">Selectează o cântare</div>'
        return
    }
    grid.innerHTML = slides.map((s, i) => `
        <div class="slide-thumb ${i===curIdx?'current':''} ${i===curIdx&&state.is_live?'live':''}"
             onclick="sendSlide(${i})">
            <span class="slide-num">${i+1}</span>
            <div class="slide-thumb-text">${escHtml(s.text || '')}</div>
        </div>`).join('')
}

function updateServiceList() {
    const list = document.getElementById('serviceList')
    const items = state.service_items || []
    if (!items.length) {
        list.innerHTML = '<div style="color:var(--subtext);text-align:center;padding:20px;">Serviciul e gol</div>'
        return
    }
    list.innerHTML = items.map((item, i) => `
        <div class="service-item" onclick="selectServiceItem(${i})">
            <span class="service-icon">${item.type==='bible'?'📖':'🎵'}</span>
            <div class="service-info">
                <div class="service-title">${escHtml(item.title)}</div>
                <div class="service-sub">Item ${i+1} din ${items.length}</div>
            </div>
        </div>`).join('')
}

function cmd(command, extra) {
    socket.emit('cmd', Object.assign({ cmd: command }, extra || {}))
    showToast(getCmdLabel(command))
}

function sendSlide(idx) {
    socket.emit('cmd', { cmd: 'go_live', idx: idx })
    switchTab('control')
}

function selectServiceItem(idx) {
    socket.emit('cmd', { cmd: 'select_service_item', idx: idx })
    switchTab('slides')
}

function toggleFreeze() {
    frozen = !frozen
    socket.emit('cmd', { cmd: frozen ? 'freeze' : 'unfreeze' })
    const btn = document.getElementById('freezeBtn')
    btn.classList.toggle('active', frozen)
    btn.style.borderColor = frozen ? 'var(--blue)' : ''
    showToast(frozen ? '❄ Display înghețat' : '▶ Display activ')
}

function toggleDisplay() {
    cmd(displayOpen ? 'close_display' : 'open_display')
}

function sendTicker() {
    const text = document.getElementById('tickerText').value.trim()
    if (!text) return
    socket.emit('cmd', { cmd: 'ticker', text: text })
    document.getElementById('tickerText').value = ''
    showToast('Ticker trimis!')
}

async function searchSongs() {
    const q = document.getElementById('songSearch').value.trim()
    const url = q ? `/api/songs/search/${encodeURIComponent(q)}` : '/api/songs'
    try {
        const r = await fetch(url)
        const songs = await r.json()
        const list = document.getElementById('songsList')
        if (!songs || !songs.length) {
            list.innerHTML = '<div style="color:var(--subtext);text-align:center;padding:20px;">Niciun rezultat</div>'
            return
        }
        list.innerHTML = songs.map(s => `
            <div class="song-item" onclick="loadSong(${s.id})">
                <div class="song-title">${escHtml(s.title)}</div>
                ${s.author ? `<div class="song-author">${escHtml(s.author)}</div>` : ''}
            </div>`).join('')
    } catch(e) {
        showToast('❌ Eroare căutare', true)
    }
}

function loadSong(songId) {
    socket.emit('cmd', { cmd: 'select_song', song_id: songId })
    switchTab('slides')
    showToast('Cântare încărcată!')
}

function switchTab(name) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'))
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'))
    const tab = document.getElementById('tab-' + name)
    if (tab) tab.classList.add('active')
    const TAB_LABELS = { control:'control', slides:'slide', service:'servi', songs:'cânt', extras:'extra' }
    document.querySelectorAll('.nav-tab').forEach(t => {
        if (t.textContent.toLowerCase().includes(TAB_LABELS[name] || name))
            t.classList.add('active')
    })
}

function escHtml(str) {
    return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')
}

function getCmdLabel(cmd) {
    const labels = {
        go_live:'▶ GO LIVE', black_screen:'⬛ Ecran Negru', clear_text:'⬜ Clear Text',
        next_slide:'→ Următor', prev_slide:'← Anterior', open_display:'📺 Display pornit',
        close_display:'📺 Display oprit', hide_ticker:'Ticker oprit',
    }
    return labels[cmd] || cmd
}

let _toastTimer = null
function showToast(msg, isError) {
    const toast = document.getElementById('toast')
    toast.textContent = msg
    toast.style.background = isError ? 'var(--red)' : 'var(--surface2)'
    toast.style.color       = isError ? '#1e1e2e'   : 'var(--text)'
    toast.classList.add('show')
    clearTimeout(_toastTimer)
    _toastTimer = setTimeout(() => toast.classList.remove('show'), 2200)
}

// Initial song list + periodic state refresh
searchSongs()
setInterval(() => {
    if (socket.connected) {
        fetch('/api/state').then(r => r.json()).then(s => { state = s; updateUI() }).catch(() => {})
    }
}, 3000)
</script>
</body>
</html>"""
