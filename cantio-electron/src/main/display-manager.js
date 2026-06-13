const { BrowserWindow, screen, app } = require('electron');
const path = require('path');
const WebSocket = require('ws');

class DisplayManager {
  constructor() {
    this.windows = new Map();
    this.wss = null;
    this.state = {
      text: '', lines: [], format: {}, settings: {},
      isBlack: false, projOff: false, frozen: false,
      tickerText: '', tickerActive: false,
      clockActive: false, timerEnd: null, timerActive: false,
      logoPath: null,
    };
    this.startWSS();
  }

  startWSS() {
    try {
      this.wss = new WebSocket.Server({ port: 7432 });
      this.wss.on('connection', (ws) => {
        ws.on('message', (raw) => {
          try {
            const msg = JSON.parse(raw);
            if (msg.type === 'ready') {
              // Send current state to new display
              this._sendState(ws);
            }
          } catch {}
        });
        ws.on('error', () => {});
      });
      this.wss.on('error', () => {});
    } catch {}
  }

  _sendState(ws) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    try {
      if (this.state.settings && Object.keys(this.state.settings).length > 0) {
        ws.send(JSON.stringify({ type: 'settings', settings: this.state.settings }));
      }
      if (this.state.text) {
        ws.send(JSON.stringify({ type: 'show_text', text: this.state.text, format: this.state.format, settings: this.state.settings }));
      }
      if (this.state.isBlack) ws.send(JSON.stringify({ type: 'black' }));
      if (this.state.projOff) ws.send(JSON.stringify({ type: 'projector_off' }));
      if (this.state.frozen) ws.send(JSON.stringify({ type: 'freeze' }));
      if (this.state.tickerActive && this.state.tickerText) {
        ws.send(JSON.stringify({ type: 'ticker', text: this.state.tickerText }));
      }
      if (this.state.clockActive) ws.send(JSON.stringify({ type: 'clock', active: true }));
      if (this.state.timerActive) {
        const remaining = Math.max(0, Math.ceil((this.state.timerEnd - Date.now()) / 1000));
        ws.send(JSON.stringify({ type: 'timer', seconds: remaining }));
      }
      if (this.state.logoPath) ws.send(JSON.stringify({ type: 'logo', path: this.state.logoPath }));
    } catch {}
  }

  broadcast(msg) {
    if (!this.wss) return;
    const data = JSON.stringify(msg);
    this.wss.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        try { client.send(data); } catch {}
      }
    });
    // Also broadcast to embedded BrowserWindows
    this.windows.forEach((win) => {
      try { win.webContents.send('render', msg); } catch {}
    });
  }

  openWindow({ screenIndex, windowId, windowName, transparent } = {}) {
    const wid = windowId || Date.now();
    if (this.windows.has(wid)) {
      this.windows.get(wid).focus();
      return { windowId: wid };
    }

    const displays = screen.getAllDisplays();
    const primary = screen.getPrimaryDisplay();
    const secondary = displays.filter(d => d.id !== primary.id);

    let targetDisplay;
    if (screenIndex === 0 && secondary.length > 0) {
      targetDisplay = secondary[0];
    } else if (screenIndex > 0 && screenIndex <= secondary.length) {
      targetDisplay = secondary[screenIndex - 1];
    } else {
      targetDisplay = displays[Math.min(screenIndex || 0, displays.length - 1)];
    }

    const bounds = targetDisplay.bounds;
    const win = new BrowserWindow({
      x: bounds.x, y: bounds.y,
      width: bounds.width, height: bounds.height,
      backgroundColor: transparent ? '#00000000' : '#000000',
      transparent: !!transparent,
      frame: false, alwaysOnTop: true, skipTaskbar: true,
      show: false,
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false,
        webSecurity: false,
      },
    });

    const displayHtml = path.join(__dirname, '..', '..', 'display', 'display.html');
    win.loadFile(displayHtml);

    win.webContents.on('did-finish-load', () => {
      win.setBounds({ x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height });
      win.show();
      setTimeout(() => win.setFullScreen(true), 200);
      win.setOpacity(0);
      const fadeStart = Date.now();
      const fade = setInterval(() => {
        const progress = Math.min(1, (Date.now() - fadeStart) / 500);
        win.setOpacity(1 - Math.pow(1 - progress, 3));
        if (progress >= 1) clearInterval(fade);
      }, 16);
    });

    win.on('closed', () => {
      this.windows.delete(wid);
      this.broadcast({ type: 'display_closed', window_id: wid });
    });

    this.windows.set(wid, win);
    return { windowId: wid };
  }

  closeWindow(windowId) {
    const win = this.windows.get(windowId);
    if (!win) return;
    let op = win.getOpacity();
    const step = () => {
      op = Math.max(0, op - 0.08);
      win.setOpacity(op);
      if (op > 0) setTimeout(step, 16);
      else win.close();
    };
    step();
  }

  showText({ screenIndex, text, format, metadata, transition, settings }) {
    this.state.text = text || '';
    this.state.lines = (text || '').split('\n');
    this.state.format = format || {};
    this.state.isBlack = false;
    this.state.projOff = false;
    if (settings) this.state.settings = { ...this.state.settings, ...settings };
    this.broadcast({
      type: 'show_text',
      text: this.state.text,
      format: this.state.format,
      metadata: metadata || {},
      transition: transition || 'fade',
      transition_duration: this.state.settings.transition_duration || 400,
      settings: settings,
    });
  }

  black(screenIndex) {
    this.state.isBlack = true;
    this.state.text = '';
    this.broadcast({ type: 'black', transition: 'fade', transition_duration: 350 });
  }

  ticker(text, settings) {
    this.state.tickerText = text || '';
    this.state.tickerActive = !!text;
    this.broadcast({ type: 'ticker', text: text || '', settings: settings || {} });
  }

  hideTicker() {
    this.state.tickerActive = false;
    this.state.tickerText = '';
    this.broadcast({ type: 'hide_ticker' });
  }

  clock(active, settings) {
    this.state.clockActive = !!active;
    this.broadcast({ type: 'clock', active: !!active, settings: settings || {} });
  }

  timer(seconds) {
    if (seconds > 0) {
      this.state.timerEnd = Date.now() + seconds * 1000;
      this.state.timerActive = true;
    } else {
      this.state.timerActive = false;
    }
    this.broadcast({ type: 'timer', seconds: seconds || 0 });
  }

  logo(logoPath) {
    this.state.logoPath = logoPath;
    this.broadcast({ type: 'logo', path: logoPath });
  }

  freeze(freeze) {
    this.state.frozen = !!freeze;
    this.broadcast({ type: freeze ? 'freeze' : 'unfreeze' });
  }

  projectorOff(off) {
    this.state.projOff = !!off;
    this.broadcast({ type: off ? 'projector_off' : 'show_text', text: this.state.text || '' });
  }

  clearText(screenIndex) {
    this.state.text = '';
    this.state.lines = [];
    this.state.isBlack = false;
    this.broadcast({ type: 'clear_text', transition: 'fade', transition_duration: 350 });
  }

  broadcastSettings(settings) {
    this.state.settings = { ...this.state.settings, ...settings };
    this.broadcast({ type: 'settings', settings: this.state.settings });
  }

  close() {
    this.windows.forEach((win) => win.close());
    this.windows.clear();
    if (this.wss) { try { this.wss.close(); } catch {} }
  }
}

module.exports = DisplayManager;
