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
const WebSocket = require('ws');

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
      openDisplay(screenIdx, window_id, windowName, isTransparent);
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
    case 'transparent':
    case 'clear_text':
    case 'freeze':
    case 'unfreeze':
    case 'ticker_advanced':
    case 'hide_ticker_effect':
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
function openDisplay(screenIdx, windowId, windowName, isTransparent = false) {
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

  const bounds = targetDisplay.bounds;

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

    // Delay fade-in cu 350 ms — Python primește window_ready și trimite conținut
    // înainte ca fade-ul să înceapă, astfel încât fade-in-ul revelează conținut, nu negru
    setTimeout(() => {
      const fadeStart = Date.now();
      const fadeDur   = 500;
      const fade = setInterval(() => {
        const progress = Math.min(1, (Date.now() - fadeStart) / fadeDur);
        const eased    = 1 - Math.pow(1 - progress, 3);   // easeOutCubic
        win.setOpacity(eased);
        if (progress >= 1) clearInterval(fade);
      }, 16);
    }, 350);
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

  if (windowId !== undefined && windowId !== null) {
    const win = windows.get(windowId);
    if (win) send(win);
  } else {
    windows.forEach((win) => send(win));
  }
}

// ── App lifecycle ─────────────────────────────────────────────────────────────
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

  startWSS();
});

app.on('window-all-closed', () => {});

app.on('before-quit', () => {
  if (wss) wss.close();
});
