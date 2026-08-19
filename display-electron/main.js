process.stdout.on('error', (e) => {})
process.stderr.on('error', (e) => {})
process.on('uncaughtException', (e) => {
  if (e.code === 'EPIPE' ||
      e.code === 'ERR_STREAM_DESTROYED' ||
      e.code === 'ERR_STREAM_WRITE_AFTER_END' ||
      (e.message && e.message.includes('pipe'))) return
  try { process.stderr.write(e.stack + '\n') } catch {}
})
process.on('unhandledRejection', () => {})

/**
 * Cantio Electron Display – main.js
 * WebSocket server on port 7432; manages one BrowserWindow per display output.
 * Accepts both "type" and "cmd" fields for backward compat.
 */

const { app, BrowserWindow, screen, ipcMain } = require('electron');
const path = require('path');
const os = require('os');
const WebSocket = require('ws');

// Cantio window/taskbar icon (bundled next to main.js). .ico on Windows for a
// crisp taskbar + title-bar icon; .png elsewhere.
const _fs = require('fs');
const CANTIO_ICON = (function () {
  for (const n of ['GProICON.ico', 'GProICON.png']) {
    const p = path.join(__dirname, n);
    try { if (_fs.existsSync(p)) return p; } catch (e) {}
  }
  return undefined;
})();

// ── GPU preference ──────────────────────────────────────────────────────────
// On hybrid-graphics laptops Chromium often picks the weak INTEGRATED GPU,
// which gets pinned at ~99% by Cantio's continuous live+preview canvas
// compositing (causing the stutter). Prefer the discrete high-performance GPU
// and keep hardware acceleration on. Unknown switches are ignored by Chromium,
// so we list both spelling variants for cross-version safety. (No-op on
// machines that only have an integrated GPU.)
try {
  app.commandLine.appendSwitch('force_high_performance_gpu');
  app.commandLine.appendSwitch('force-high-performance-gpu');
  app.commandLine.appendSwitch('ignore-gpu-blocklist');
  // Dynamic presentations play audio programmatically (no click) — allow it.
  app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');
} catch (e) {}

// Dedicated background-editor mode detection (must run before app is ready so
// we can give this process its OWN userData dir — otherwise two Electron
// instances fight over the same cache lock and the editor window fails to init).
const _bgEditorArg  = process.argv.find(a => a.startsWith('--bg-editor='));
const _bgEditorOnly = !!_bgEditorArg;
if (_bgEditorOnly) {
  try {
    app.setPath('userData', path.join(os.tmpdir(), 'cantio-bg-editor'));
  } catch (e) {}
}

// ── State ─────────────────────────────────────────────────────────────────────
const windows = new Map();   // window_id → BrowserWindow
let wss = null;

// ── WebSocket server ──────────────────────────────────────────────────────────
function startWSS() {
  wss = new WebSocket.Server({ port: 7432 });

  wss.on('connection', (ws) => {
    //log: Python connected

    ws.on('message', (raw) => {
      let msg;
      try { msg = JSON.parse(raw); } catch { return; }
      const reply = handleCommand(msg, ws);
      if (reply !== undefined) {
        try { ws.send(JSON.stringify(reply)); } catch {}
      }
    });

    ws.on('close', () => {});
    ws.on('error', () => {});

    try {
      ws.send(JSON.stringify({ type: 'ready', screens: getScreenList() }));
    } catch {}
  });

  wss.on('error', () => {});
}

// ── Screen list ───────────────────────────────────────────────────────────────
function getScreenList() {
  const primaryId   = screen.getPrimaryDisplay().id;
  const all         = screen.getAllDisplays();
  const secondaries = all.filter(d => d.id !== primaryId);
  return all.map((d, i) => {
    const isPrimary    = d.id === primaryId;
    const secIdx       = secondaries.findIndex(s => s.id === d.id);  // -1 if primary
    return {
      index:       i,
      id:          d.id,
      label:       d.label || `Display ${i + 1}`,
      name:        isPrimary ? 'Primary' : `Screen ${secIdx + 1}`,
      bounds:      d.bounds,
      width:       d.bounds.width,
      height:      d.bounds.height,
      x:           d.bounds.x,
      y:           d.bounds.y,
      primary:     isPrimary,
      scaleFactor: d.scaleFactor || 1,
      // screen_index compatibil cu openDisplay(): secondary-first indexing
      screen_index: isPrimary ? 0 : secIdx + 1,
    };
  });
}

// ── Command router ────────────────────────────────────────────────────────────
function handleCommand(msg, ws) {
  const type      = msg.type || msg.cmd;
  const window_id = msg.window_id;

  switch (type) {
    case 'ping':
      return { type: 'pong', resp: 'pong' };

    case 'get_screens':
      return { type: 'screens', screens: getScreenList() };

    case 'open': {
      const screenIdx     = msg.screen_index !== undefined ? msg.screen_index : (msg.screen_idx || 0);
      const windowName    = msg.window_name  || `Display ${window_id}`;
      const isTransparent = msg.transparent === true || msg.transparent === 'true';
      openDisplay(screenIdx, window_id, windowName, isTransparent,
                  parseInt(msg.custom_w) || 0, parseInt(msg.custom_h) || 0);
      return { type: 'ok', window_id };
    }

    case 'set_transparent': {
      // Transparent must be set at window creation time on Windows.
      // Close the old window and reopen with transparent:true / false.
      const wid        = msg.window_id !== undefined ? msg.window_id : window_id;
      const screenIdx  = msg.screen_index !== undefined ? msg.screen_index : (msg.screen_idx || 0);
      const wantTrans  = msg.value === true || msg.value === 'true';
      if (windows.has(wid)) {
        const old = windows.get(wid);
        windows.delete(wid);
        old.close();
      }
      setTimeout(() => openDisplay(screenIdx, wid, `Display ${wid}`, wantTrans), 350);
      return { type: 'ok', window_id: wid };
    }

    case 'close':
      closeDisplay(window_id);
      return { type: 'ok', window_id };

    case 'open_bg_editor': {
      openBgEditor(msg.file || '');
      return { type: 'ok' };
    }

    case 'open_theme_editor': {
      openThemeEditor(msg.file || '');
      return { type: 'ok' };
    }

    case 'open_preview': {
      openPreview();
      return { type: 'ok' };
    }

    case 'close_preview': {
      if (previewWin && !previewWin.isDestroyed()) previewWin.close();
      previewWin = null;
      return { type: 'ok' };
    }

    case 'render_thumb': {
      // Render a bg-engine slide doc to a PNG (WYSIWYG operator thumbnail) using
      // an ALREADY-running renderer (preview, else a live window) — no new proc.
      const win = (previewWin && !previewWin.isDestroyed())
        ? previewWin
        : (windows.size ? windows.values().next().value : null);
      if (win && !win.isDestroyed()) {
        const js = 'window._renderThumb ? window._renderThumb('
          + JSON.stringify(msg.doc) + ',' + (msg.w | 0) + ',' + (msg.h | 0) + ") : ''";
        win.webContents.executeJavaScript(js).then((url) => {
          if (wss && url) {
            const data = JSON.stringify({ type: 'thumb_result', id: msg.id, dataURL: url });
            wss.clients.forEach(c => { if (c.readyState === WebSocket.OPEN) { try { c.send(data); } catch {} } });
          }
        }).catch(() => {});
      }
      return { type: 'ok' };
    }

    case 'quit':
      setTimeout(() => app.quit(), 200);
      return { type: 'ok' };

    case 'show_text':
    case 'black':
    case 'settings':
    case 'ticker':
    case 'hide_ticker':
    case 'timer':
    case 'stop_timer':
    case 'clock':
    case 'projector_off':
    case 'logo':
    case 'slide_image':
    case 'show_slide_image':
    case 'show_web':
    case 'hide_web':
    case 'transparent':
    case 'clear_text':
    case 'freeze':
    case 'unfreeze':
    case 'ticker_advanced':
    case 'hide_ticker_effect':
    case 'show_background':
    case 'clear_background':
    case 'show_presentation_slide':
    case 'clear_presentation':
    case 'dim':
    case 'manual_prep':
    case 'manual_set':
    case 'manual_end':
    case 'dynamic_play':
    case 'dynamic_stop':
    case 'audio_pause':
    case 'audio_resume':
    case 'audio_volume':
    case 'audio_seek':
    case 'audio_bin_play':
    case 'audio_bin_pause':
    case 'audio_bin_resume':
    case 'audio_bin_stop':
    case 'audio_bin_volume':
      broadcast(window_id, msg);
      return { type: 'ok', window_id };

    // settings packet that also carries bg_transparent flag — handled by renderer
    // (set_transparent recreates the window; 'settings' just pushes CSS changes)
    case 'apply_transparent_settings': {
      broadcast(window_id, { ...msg, type: 'settings' });
      return { type: 'ok', window_id };
    }

    default:
      return { type: 'error', message: `Unknown command: ${type}` };
  }
}

// ── Open display window ───────────────────────────────────────────────────────
function openDisplay(screenIdx, windowId, windowName, isTransparent = false,
                     customW = 0, customH = 0) {
  if (windows.has(windowId)) {
    windows.get(windowId).focus();
    return;
  }

  const displays        = screen.getAllDisplays();
  const primaryDisplay  = screen.getPrimaryDisplay();
  const secondaryDisplays = displays.filter(d => d.id !== primaryDisplay.id);

  // Log pentru debugging
  console.log(`[Display] openDisplay: screenIdx=${screenIdx}, displays=${displays.length}, secondary=${secondaryDisplays.length}`);
  displays.forEach((d, i) => {
    const isPrimary = d.id === primaryDisplay.id;
    console.log(`[Display]   Screen ${i}: ${d.bounds.width}×${d.bounds.height} @ (${d.bounds.x},${d.bounds.y}) ${isPrimary ? '[PRIMARY]' : '[secondary]'}`);
  });

  // Selectare ecran: aceeași logică ca ElectronDisplayManager.open_display() din Python
  //   screenIdx 0 → primul ecran secundar (non-primary)
  //   screenIdx 1 → primul ecran secundar (1-based, compatibil cu Settings "Screen 1")
  //   fallback    → indexare directă
  let targetDisplay;
  if (screenIdx === 0 && secondaryDisplays.length > 0) {
    targetDisplay = secondaryDisplays[0];
  } else if (screenIdx > 0 && screenIdx <= secondaryDisplays.length) {
    targetDisplay = secondaryDisplays[screenIdx - 1];
  } else {
    // Fallback: folosește indexul direct (include primary)
    targetDisplay = displays[Math.min(screenIdx, displays.length - 1)];
  }

  console.log(`[Display] Target: ${targetDisplay.bounds.width}×${targetDisplay.bounds.height} @ (${targetDisplay.bounds.x},${targetDisplay.bounds.y})`);

  const scr = targetDisplay.bounds;
  // Custom resolution → a windowed output of that exact size, centred on the target
  // screen (not fullscreen). Otherwise fill the screen as before.
  const useCustom = customW > 0 && customH > 0;
  const bounds = useCustom ? {
    x:      scr.x + Math.max(0, Math.round((scr.width  - customW) / 2)),
    y:      scr.y + Math.max(0, Math.round((scr.height - customH) / 2)),
    width:  customW,
    height: customH,
  } : scr;

  const win = new BrowserWindow({
    x:               bounds.x,
    y:               bounds.y,
    width:           bounds.width,
    height:          bounds.height,
    backgroundColor: isTransparent ? '#00000000' : '#000000',
    transparent:     isTransparent,
    frame:           false,
    alwaysOnTop:     true,
    skipTaskbar:     true,
    show:            false,
    webPreferences: {
      nodeIntegration:             true,
      contextIsolation:            false,
      webSecurity:                 false,
      allowRunningInsecureContent: true,
      experimentalFeatures:        true,
    },
  });

  win.loadFile(path.join(__dirname, 'display.html'));

  win.webContents.on('did-finish-load', () => {
    // Setează bounds explicit după load pentru a asigura poziția corectă
    win.setBounds({
      x:      bounds.x,
      y:      bounds.y,
      width:  bounds.width,
      height: bounds.height,
    });

    win.setOpacity(0);
    win.show();

    setTimeout(() => {
      win.setBounds({ x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height });
    }, 150);

    // Notifică Python că fereastra e gata să primească conținut
    const readyMsg = JSON.stringify({ type: 'window_ready', window_id: windowId });
    if (wss) {
      wss.clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
          try { client.send(readyMsg); } catch {}
        }
      });
    }

    // Fade-in starts only after the renderer signals it has drawn the first frame
    // (via ipcRenderer.send('frame_rendered')), so the window never reveals black.
    // A 700 ms fallback covers cases where the signal is missed.
    let _fadeDone = false;
    let _ipcListener = null;
    const _startFade = () => {
      if (_fadeDone) return;
      _fadeDone = true;
      if (_ipcListener) { ipcMain.removeListener('frame_rendered', _ipcListener); _ipcListener = null; }
      const fadeStart = Date.now();
      const fadeDur   = 500;
      const fade = setInterval(() => {
        const progress = Math.min(1, (Date.now() - fadeStart) / fadeDur);
        const eased    = 1 - Math.pow(1 - progress, 3);   // easeOutCubic
        win.setOpacity(eased);
        if (progress >= 1) clearInterval(fade);
      }, 16);
    };
    _ipcListener = (event) => {
      if (event.sender === win.webContents) _startFade();
    };
    ipcMain.on('frame_rendered', _ipcListener);
    setTimeout(_startFade, 700);
  });

  win.webContents.on('render-process-gone', () => {});

  win.on('closed', () => {
    windows.delete(windowId);
    if (wss) {
      wss.clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
          try {
            client.send(JSON.stringify({ type: 'display_closed', window_id: windowId }));
          } catch {}
        }
      });
    }
  });

  windows.set(windowId, win);
  return win;
}

// ── Operator preview window (same Chromium, mirrors live content) ────────────
// Frameless + off-screen; its native HWND is sent to Python which embeds it into
// the PyQt UI (createWindowContainer). Falls back to floating if not embedded.
let previewWin = null;
function _sendPreviewHwnd() {
  if (!previewWin || previewWin.isDestroyed() || !wss) return;
  try {
    const buf = previewWin.getNativeWindowHandle();
    let hwnd;
    if (buf.length >= 8) hwnd = Number(buf.readBigInt64LE(0));
    else                 hwnd = buf.readInt32LE(0);
    const data = JSON.stringify({ type: 'preview_hwnd', hwnd });
    wss.clients.forEach(c => { if (c.readyState === WebSocket.OPEN) { try { c.send(data); } catch {} } });
  } catch (e) {}
}
function openPreview() {
  if (previewWin && !previewWin.isDestroyed()) { _sendPreviewHwnd(); return previewWin; }
  previewWin = new BrowserWindow({
    width: 520, height: 300,
    x: -3000, y: -3000,           // off-screen until Qt reparents it
    backgroundColor: '#000000',
    title: 'Cantio Preview',
    frame: false,
    show: false,
    skipTaskbar: true,
    alwaysOnTop: false,
    webPreferences: {
      nodeIntegration: true, contextIsolation: false,
      webSecurity: false, allowRunningInsecureContent: true,
    },
  });
  previewWin.loadFile(path.join(__dirname, 'display.html'), { query: { preview: '1' } });
  previewWin.webContents.once('did-finish-load', () => {
    try { previewWin.showInactive(); } catch (e) {}
    _sendPreviewHwnd();
    // Re-send a couple of times in case Python connected slightly later
    setTimeout(_sendPreviewHwnd, 400);
    setTimeout(_sendPreviewHwnd, 1200);
  });
  previewWin.on('closed', () => { previewWin = null; });
  return previewWin;
}

// ── Background editor window ────────────────────────────────────────────────
let bgEditorWin = null;
function openBgEditor(filePath) {
  if (bgEditorWin && !bgEditorWin.isDestroyed()) {
    bgEditorWin.focus();
    // Reload with the new file if a different background was requested
    bgEditorWin.loadFile(path.join(__dirname, 'background-editor.html'),
      { query: { file: filePath } });
    return bgEditorWin;
  }
  const primary = screen.getPrimaryDisplay();
  const b = primary.workArea;
  bgEditorWin = new BrowserWindow({
    width:  Math.min(1500, b.width  - 80),
    height: Math.min(900,  b.height - 80),
    center: true,
    backgroundColor: '#181818',
    title: 'Cantio — Editor Fundal',
    icon: CANTIO_ICON,
    autoHideMenuBar: true,
    skipTaskbar: false,   // show in the Windows taskbar
    show: true,           // visible immediately (don't depend on ready-to-show)
    webPreferences: {
      nodeIntegration:  true,
      contextIsolation: false,
      webSecurity:      false,
      allowRunningInsecureContent: true,
    },
  });

  const htmlPath = path.join(__dirname, 'background-editor.html');
  bgEditorWin.loadFile(htmlPath, { query: { file: filePath } })
    .catch(err => console.error('[BGEditor] loadFile failed:', err));

  // Diagnostics — surface any load failure in the editor log.
  bgEditorWin.webContents.on('did-fail-load', (_e, code, desc, url) => {
    console.error(`[BGEditor] did-fail-load ${code} ${desc} ${url}`);
  });

  // Bring it to the front (it otherwise opens behind the Cantio window).
  const _toFront = () => {
    if (!bgEditorWin || bgEditorWin.isDestroyed()) return;
    bgEditorWin.show();
    bgEditorWin.setAlwaysOnTop(true);
    bgEditorWin.focus();
    setTimeout(() => { try { bgEditorWin.setAlwaysOnTop(false); } catch (e) {} }, 500);
  };
  bgEditorWin.once('ready-to-show', _toFront);
  bgEditorWin.webContents.once('did-finish-load', _toFront);  // fallback
  setTimeout(_toFront, 1200);                                  // last-resort fallback

  bgEditorWin.on('closed', () => { bgEditorWin = null; });
  return bgEditorWin;
}

// ── Theme editor window (full Electron, live render + sample text) ──────────────
let themeEditorWin = null;
function openThemeEditor(filePath) {
  if (themeEditorWin && !themeEditorWin.isDestroyed()) {
    themeEditorWin.focus();
    themeEditorWin.loadFile(path.join(__dirname, 'theme-editor.html'),
      { query: { file: filePath } });
    return themeEditorWin;
  }
  const primary = screen.getPrimaryDisplay();
  const b = primary.workArea;
  themeEditorWin = new BrowserWindow({
    width:  Math.min(1400, b.width  - 80),
    height: Math.min(860,  b.height - 80),
    center: true,
    backgroundColor: '#14141c',
    title: 'Cantio — Editor Teme',
    icon: CANTIO_ICON,
    autoHideMenuBar: true,
    skipTaskbar: false,
    show: true,
    webPreferences: {
      nodeIntegration:  true,
      contextIsolation: false,
      webSecurity:      false,
      allowRunningInsecureContent: true,
    },
  });
  themeEditorWin.loadFile(path.join(__dirname, 'theme-editor.html'),
    { query: { file: filePath } })
    .catch(err => console.error('[ThemeEditor] loadFile failed:', err));
  const _toFront = () => {
    if (!themeEditorWin || themeEditorWin.isDestroyed()) return;
    themeEditorWin.show(); themeEditorWin.setAlwaysOnTop(true); themeEditorWin.focus();
    setTimeout(() => { try { themeEditorWin.setAlwaysOnTop(false); } catch (e) {} }, 500);
  };
  themeEditorWin.once('ready-to-show', _toFront);
  themeEditorWin.webContents.once('did-finish-load', _toFront);
  setTimeout(_toFront, 1200);
  themeEditorWin.on('closed', () => { themeEditorWin = null; });
  return themeEditorWin;
}

ipcMain.on('theme_saved', (_e, name) => {
  if (!wss) return;
  const data = JSON.stringify({ type: 'theme_saved', name });
  wss.clients.forEach(c => { if (c.readyState === WebSocket.OPEN) { try { c.send(data); } catch {} } });
});

// Relay editor save events to Python WS clients (so the list can refresh).
ipcMain.on('bg_saved', (_e, file) => {
  if (!wss) return;
  const data = JSON.stringify({ type: 'bg_saved', file });
  wss.clients.forEach(c => { if (c.readyState === WebSocket.OPEN) { try { c.send(data); } catch {} } });
});

// Dynamic presentation auto-advanced to a new slide → tell Python so the
// operator's thumbnail strip follows along (and they can intervene).
ipcMain.on('dynamic_slide', (_e, index) => {
  if (!wss) return;
  const data = JSON.stringify({ type: 'dynamic_slide', index });
  wss.clients.forEach(c => { if (c.readyState === WebSocket.OPEN) { try { c.send(data); } catch {} } });
});

// ── Close display window ──────────────────────────────────────────────────────
function closeDisplay(windowId) {
  const win = windows.get(windowId);
  if (!win) return;

  let op = win.getOpacity();
  const step = () => {
    op = Math.max(0, op - 0.08);
    win.setOpacity(op);
    if (op > 0) {
      setTimeout(step, 16);
    } else {
      win.close();
    }
  };
  step();
}

// ── Broadcast to renderer ─────────────────────────────────────────────────────
function broadcast(windowId, msg) {
  const data = JSON.stringify(msg);

  const send = (win) => {
    if (win.isDestroyed()) return;

    try {
      win.webContents.send('render', msg);
    } catch {}

    const js = `if(typeof window._handleRender==='function')window._handleRender(${data})`;
    win.webContents.executeJavaScript(js).catch(() => {});
  };

  // Audio/dynamic messages must hit exactly ONE window or the track plays twice
  // (live + mirrored preview = echo). They route explicitly by window_id.
  const AUDIO_TYPES = ['dynamic_play', 'dynamic_stop', 'audio_pause',
                       'audio_resume', 'audio_volume', 'audio_seek',
                       'audio_bin_play', 'audio_bin_pause', 'audio_bin_resume',
                       'audio_bin_stop', 'audio_bin_volume'];
  const isAudio = AUDIO_TYPES.indexOf(msg && msg.type) !== -1;

  // window_id -1 = operator-preview-only target (no live window uses that id).
  if (windowId === -1) {
    if (previewWin && !previewWin.isDestroyed()) send(previewWin);
    return;
  }

  if (windowId !== undefined && windowId !== null) {
    const win = windows.get(windowId);
    if (win) send(win);
  } else {
    windows.forEach((win) => send(win));
  }

  // Mirror content to the operator-preview window so it shows what the projector
  // shows — but NOT audio/dynamic (those would create a second, echoing player).
  if (!isAudio && previewWin && !previewWin.isDestroyed()) send(previewWin);
}

// ── App lifecycle ─────────────────────────────────────────────────────────────
// Dedicated background-editor mode (computed at top of file): launched as its
// own process with `electron . --bg-editor=<file>`. Opens ONLY the editor
// (no WS server), so it never collides with the live-display process on port
// 7432 and always loads the on-disk editor files.

app.whenReady().then(() => {
  // Allow camera / microphone access from renderer pages (needed for bg camera)
  const { session } = require('electron');
  session.defaultSession.setPermissionRequestHandler(
    (webContents, permission, callback) => {
      if (permission === 'media' ||
          permission === 'camera' ||
          permission === 'microphone' ||
          permission === 'display-capture') {
        callback(true);
      } else {
        callback(false);
      }
    }
  );

  if (_bgEditorOnly) {
    const file = decodeURIComponent(_bgEditorArg.slice('--bg-editor='.length));
    openBgEditor(file);
    return;   // editor-only process: do NOT start the WebSocket server
  }

  startWSS();
});

app.on('window-all-closed', () => {
  // The dedicated editor process should exit when its window closes.
  if (_bgEditorOnly) app.quit();
});

app.on('before-quit', () => {
  if (wss) wss.close();
});
