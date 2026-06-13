/**
 * Cantio Electron Display – display.js
 * Renderer process: receives IPC 'render' events and paints to canvas.
 */

'use strict';

const { ipcRenderer } = require('electron');

console.log('[Display.js] Script încărcat!');

// ── Canvas setup ─────────────────────────────────────────────────────────────
const cvPrev  = document.getElementById('canvas-prev');
const cvCurr  = document.getElementById('canvas-curr');
const bgVideo = document.getElementById('bg-video');
const bgImage = document.getElementById('bg-image');

if (!cvPrev || !cvCurr) {
  console.error('[Display.js] ❌ Canvas elements NOT FOUND în DOM!');
}

const ctxP = cvPrev ? cvPrev.getContext('2d') : null;
const ctxC = cvCurr ? cvCurr.getContext('2d') : null;

if (!ctxC) console.error('[Display.js] ❌ CTX NULL!');

// ── Resize ────────────────────────────────────────────────────────────────────
function resize() {
  if (!cvPrev || !cvCurr) return;
  cvPrev.width  = cvCurr.width  = window.innerWidth;
  cvPrev.height = cvCurr.height = window.innerHeight;
  console.log('[Display.js] Resize:', cvCurr.width, 'x', cvCurr.height);
}

window.addEventListener('resize', () => { resize(); renderCurrent(); });

// ── State ─────────────────────────────────────────────────────────────────────
let state = {
  text:         '',
  lines:        [],
  format:       {},
  settings:     {},
  metadata:     {},   // bible reference, source, etc.
  isBlack:      false,
  tickerText:   '',
  tickerActive: false,
  clockActive:  false,
  timerEnd:     null,
  timerActive:  false,
  logoPath:     null,
  projOff:      false,
  frozen:       false,   // true → all render commands are ignored
};

// Transition
let transition = { active: false, type: 'fade', duration: 400, start: 0, progress: 1 };

// Ticker scroll
let tickerX    = 0;
let lastTickTs = 0;

// ── Ticker display settings (updated by each 'ticker' / 'ticker_advanced' cmd)
let tickerSettings = {
  speed:       3,
  font_size:   22,
  font_family: 'Arial',
  text_color:  '#f9e2af',
  bg_color:    'rgba(0,0,0,0.85)',
  bar_height:  52,
  position:    'bottom',
};

// ── Ticker animation state ────────────────────────────────────────────────────
let tickerState = {
  barY:      null,   // current Y position (null = not yet placed)
  targetY:   null,   // target Y (final resting position)
  animating: false,
  barOpacity: 1.0,
  slideDir:  null,   // 'in' | 'out'
  animStart: 0,
  animDur:   400,
  onDone:    null,   // callback when animation completes
};

// Logo image cache
const logoCache = {};

// ── Animated gradient state ───────────────────────────────────────────────────
let gradientAnim = {
  time:   0,
  colors: ['#1a237e', '#6a1b9a', '#0d47a1'],
  speed:  0.5,
};

// ── Visual self-test (fires immediately on load) ──────────────────────────────
function testRender() {
  if (!ctxC) return;
  const W = cvCurr.width  || window.innerWidth  || 1920;
  const H = cvCurr.height || window.innerHeight || 1080;
  console.log('[Display.js] testRender', W, 'x', H);
  ctxC.fillStyle = '#000033';
  ctxC.fillRect(0, 0, W, H);
  ctxC.fillStyle = '#ffffff';
  ctxC.font = 'bold 48px Arial, sans-serif';
  ctxC.textAlign = 'center';
  ctxC.textBaseline = 'middle';
  ctxC.fillText('Cantio Display — Gata', W / 2, H / 2);
  console.log('[Display.js] testRender OK');
}

// ── DOM ready ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  console.log('[Display.js] DOMContentLoaded');
  resize();
  testRender();
  requestAnimationFrame(mainLoop);
});

// Fallback: run immediately if DOM already ready
if (document.readyState !== 'loading') {
  resize();
  testRender();
  requestAnimationFrame(mainLoop);
}

// ── IPC listener (Metodă 1 — principală) ─────────────────────────────────────
ipcRenderer.on('render', (_event, msg) => {
  console.log('[Display.js] IPC render:', msg.type || msg.cmd,
    msg.text ? `"${msg.text.slice(0, 40)}"` : '',
    msg.settings ? '(settings)' : '');
  handleMessage(msg);
});

// ── Global fallback (Metodă 2 — executeJavaScript din main) ──────────────────
window._handleRender = function (msg) {
  console.log('[Display.js] _handleRender (fallback):', msg.type || msg.cmd);
  handleMessage(msg);
};

// ── Message dispatcher ────────────────────────────────────────────────────────
function handleMessage(msg) {
  // Accept both "type" and "cmd"
  const type = msg.type || msg.cmd;

  // ── Freeze guard: ignore all commands while frozen except unfreeze / quit ──
  if (state.frozen && type !== 'unfreeze' && type !== 'quit') {
    console.log('[Display.js] FROZEN — ignoring:', type);
    return;
  }

  switch (type) {

    case 'freeze': {
      state.frozen = true;
      console.log('[Display.js] Display FROZEN — canvas locked');
      break;
    }

    case 'unfreeze': {
      state.frozen = false;
      console.log('[Display.js] Display UNFROZEN — resuming render');
      renderCurrent();
      break;
    }

    case 'clear_text': {
      // Clear text + metadata but keep background, settings, ticker, clock etc.
      capturePrev();
      state.text     = '';
      state.lines    = [];
      state.metadata = {};
      state.isBlack  = false;
      const clearTType = state.settings.transition || 'fade';
      const clearTDur  = parseInt(state.settings.transition_duration || 350, 10);
      if (clearTType === 'instant' || clearTType === 'none') {
        renderCurrent();
      } else {
        startTransition(clearTType, clearTDur);
      }
      console.log('[Display.js] clear_text — text and metadata cleared');
      break;
    }

    case 'show_text': {
      console.log('[Display.js] show_text — text:',
        (msg.text || '').slice(0, 60),
        '| settings:', JSON.stringify(msg.settings || {}).slice(0, 200));

      // If settings are bundled with the show_text call, apply them first
      if (msg.settings && Object.keys(msg.settings).length > 0) {
        state.settings = { ...state.settings, ...msg.settings };
        applyBackground(state.settings);
      }
      // Save metadata (bible reference, source, copyright, etc.)
      if (msg.metadata) {
        state.metadata = msg.metadata;
      }
      capturePrev();
      state.text    = msg.text || '';
      state.lines   = state.text.split('\n');
      state.format  = msg.format || {};
      state.isBlack = false;
      state.projOff = false;
      dualState.active = false;   // exit dual-language mode

      const transType = msg.transition
        || state.settings.transition
        || 'fade';
      const transDur = parseInt(
        msg.transition_duration
        || msg.transition_duration_ms
        || state.settings.transition_duration
        || state.settings.transition_duration_ms
        || 400, 10);

      if (transType === 'instant' || transType === 'none') {
        renderCurrent();
      } else {
        startTransition(transType, transDur);
      }
      console.log('[Display.js] show_text OK — linii:', state.lines.length,
        'trans:', transType, 'dur:', transDur);
      break;
    }

    case 'black': {
      capturePrev();
      state.isBlack    = true;
      state.text       = '';
      state.lines      = [];
      dualState.active = false;
      const blackTType = state.settings.transition || 'fade';
      const blackTDur  = parseInt(state.settings.transition_duration || 350, 10);
      if (blackTType === 'instant' || blackTType === 'none') {
        renderCurrent();
      } else {
        startTransition(blackTType, blackTDur);
      }
      break;
    }

    case 'projector_off': {
      capturePrev();
      state.projOff = true;
      state.isBlack = false;
      state.text    = '';
      state.lines   = [];
      startTransition('fade', 300);
      break;
    }

    case 'settings': {
      const incoming = msg.settings || {};
      state.settings = { ...state.settings, ...incoming };
      console.log('[Display.js] settings aplicat — bg_type:', state.settings.bg_type,
        'bg_color:', state.settings.bg_color,
        'font_size:', state.settings.font_size,
        'bold:', state.settings.bold ?? state.settings.font_bold,
        'text_color:', state.settings.text_color || state.settings.font_color);
      applyBackground(state.settings);
      renderCurrent();
      break;
    }

    case 'ticker': {
      state.tickerText   = msg.text || '';
      state.tickerActive = true;
      tickerX = cvCurr ? cvCurr.width : window.innerWidth;
      if (msg.settings && Object.keys(msg.settings).length > 0) {
        tickerSettings = { ...tickerSettings, ...msg.settings };
      }
      // Reset ticker state for instant show
      tickerState.barY      = null;
      tickerState.animating = false;
      tickerState.barOpacity = 1.0;
      break;
    }

    case 'hide_ticker': {
      state.tickerActive = false;
      state.tickerText   = '';
      tickerState.barY   = null;
      tickerState.animating = false;
      renderCurrent();
      break;
    }

    case 'ticker_advanced': {
      // Ticker with slide-up animation
      const inEffect = (msg.settings && msg.settings.ticker_in_effect) || 'slide_up';
      state.tickerText   = msg.text || '';
      state.tickerActive = true;
      tickerX = cvCurr ? cvCurr.width : window.innerWidth;
      if (msg.settings && Object.keys(msg.settings).length > 0) {
        tickerSettings = { ...tickerSettings, ...msg.settings };
      }
      showTickerWithEffect(inEffect, parseInt(msg.settings && msg.settings.ticker_duration || 400));
      break;
    }

    case 'hide_ticker_effect': {
      const outEffect = (msg.settings && msg.settings.ticker_out_effect) || 'slide_down';
      hideTickerWithEffect(outEffect, parseInt(msg.settings && msg.settings.ticker_duration || 400));
      break;
    }

    case 'timer': {
      const secs        = msg.seconds || 0;
      state.timerEnd    = Date.now() + secs * 1000;
      state.timerActive = true;
      break;
    }

    case 'stop_timer': {
      state.timerActive = false;
      renderCurrent();
      break;
    }

    case 'clock': {
      state.clockActive = msg.active !== false;
      if (msg.settings && Object.keys(msg.settings).length > 0) {
        state.settings.clock = { ...(state.settings.clock || {}), ...msg.settings };
      }
      renderCurrent();
      break;
    }

    case 'logo': {
      const lp = msg.path || null;
      state.logoPath = lp;
      if (lp && !logoCache[lp]) {
        const img  = new Image();
        img.onload  = () => { logoCache[lp] = img; renderCurrent(); };
        img.onerror = () => { console.warn('[Display.js] Logo load failed:', lp); logoCache[lp] = null; };
        img.src = lp.startsWith('file://') ? lp : `file://${lp}`;
      } else {
        renderCurrent();
      }
      break;
    }

    case 'slide_image':
    case 'show_slide_image': {
      const imgPath = msg.path || '';
      if (imgPath && bgImage) {
        if (bgVideo) bgVideo.style.display = 'none';
        bgImage.src = imgPath.startsWith('file://') ? imgPath : `file://${imgPath}`;
        bgImage.style.display = 'block';
      }
      capturePrev();
      state.text    = '';
      state.lines   = [];
      state.isBlack = false;
      startTransition('fade', 300);
      break;
    }

    case 'transparent': {
      // msg.value == true → transparent mode; false → opaque
      const wantTrans = msg.value === true || msg.value === 'true';
      if (wantTrans) {
        document.body.style.background     = 'transparent';
        document.body.style.backgroundColor = 'transparent';
        if (cvCurr) cvCurr.style.background = 'transparent';
        if (cvPrev) cvPrev.style.background = 'transparent';
      } else {
        document.body.style.background     = '#000000';
        document.body.style.backgroundColor = '#000000';
        if (cvCurr) cvCurr.style.background = '';
        if (cvPrev) cvPrev.style.background = '';
      }
      break;
    }

    case 'show_dual': {
      console.log('[Display.js] show_dual — original:',
        (msg.original || '').slice(0, 40),
        '| translated:', (msg.translated || '').slice(0, 40));
      if (msg.settings && Object.keys(msg.settings).length > 0) {
        state.settings = { ...state.settings, ...msg.settings };
        applyBackground(state.settings);
      }
      capturePrev();
      dualState.active     = true;
      dualState.original   = msg.original   || '';
      dualState.translated = msg.translated || '';
      dualState.layout     = msg.layout     || {};
      state.isBlack        = false;
      state.projOff        = false;
      state.text           = '';
      state.lines          = [];
      const dualTrans = msg.transition || state.settings.transition || 'fade';
      const dualDur   = parseInt(msg.transition_duration || state.settings.transition_duration || 400, 10);
      if (dualTrans === 'instant' || dualTrans === 'none') {
        renderCurrent();
      } else {
        startTransition(dualTrans, dualDur);
      }
      break;
    }

    case 'hide_dual': {
      capturePrev();
      dualState.active = false;
      startTransition('fade', 300);
      break;
    }

    default:
      console.warn('[Display.js] Tip mesaj necunoscut:', type);
  }
}

// ── Background ────────────────────────────────────────────────────────────────

function applyBackground(s) {
  if (!s) return;

  const bg       = (s.bg_image || '').trim();
  const bgType   = s.bg_type   || 'color';
  const bgColor  = s.bg_color  || '#000000';
  const bgOpacity = parseFloat(s.bg_opacity || 1.0);

  // Always set body colour (fallback behind any media element)
  document.body.style.backgroundColor = bgColor;

  // ── Helper: Windows path → file:/// URL ──────────────────────────────────
  function fixPath(p) {
    if (!p) return '';
    let f = p.replace(/\\/g, '/');
    f = f.replace(/^file:\/{1,3}/, '');   // strip any existing file:// prefix
    return 'file:///' + f;
  }

  // ── No media file → clear and return ─────────────────────────────────────
  if (!bg || bg === 'None' || bg === 'null') {
    if (bgVideo) {
      bgVideo.pause();
      bgVideo.style.display = 'none';
      bgVideo.src = '';
      bgVideo.srcObject = null;
    }
    if (bgImage) {
      bgImage.style.display = 'none';
      bgImage.src = '';
    }
    return;
  }

  const ext     = bg.split('.').pop().toLowerCase();
  const isVideo = ['mp4','mov','avi','mkv','webm','m4v'].includes(ext);

  // ── Camera ────────────────────────────────────────────────────────────────
  if (bgType === 'camera') {
    if (bgImage) bgImage.style.display = 'none';
    if (bgVideo) {
      bgVideo.style.display   = 'block';
      bgVideo.style.opacity   = bgOpacity;
      bgVideo.srcObject       = null;
      bgVideo.src             = '';
    }
    const camIdx = parseInt(bg);
    navigator.mediaDevices.enumerateDevices()
      .then(devices => {
        const cameras = devices.filter(d => d.kind === 'videoinput');
        const cam     = isNaN(camIdx)
          ? cameras.find(c => c.deviceId === bg)
          : cameras[camIdx];
        if (!cam) return Promise.reject(new Error('camera not found'));
        return navigator.mediaDevices.getUserMedia({
          video: { deviceId: { exact: cam.deviceId } },
        });
      })
      .then(stream => {
        if (bgVideo) { bgVideo.srcObject = stream; bgVideo.play().catch(() => {}); }
      })
      .catch(() => {});
    return;
  }

  // ── Video file ────────────────────────────────────────────────────────────
  if (isVideo) {
    if (bgImage) bgImage.style.display = 'none';
    if (bgVideo) {
      bgVideo.style.display = 'block';
      bgVideo.style.opacity = bgOpacity;
      bgVideo.srcObject     = null;
      const fixedPath = fixPath(bg);
      // Avoid reloading if same source
      if (!bgVideo.src.includes(bg.replace(/\\/g, '/'))) {
        bgVideo.src = fixedPath;
        bgVideo.load();
      }
      bgVideo.play().catch(() => {
        setTimeout(() => bgVideo.play().catch(() => {}), 500);
      });
    }
    return;
  }

  // ── Static image ──────────────────────────────────────────────────────────
  if (bgVideo) {
    bgVideo.pause();
    bgVideo.style.display = 'none';
    bgVideo.src           = '';
    bgVideo.srcObject     = null;
  }
  if (bgImage) {
    const fixedPath        = fixPath(bg);
    bgImage.src            = fixedPath;
    bgImage.style.opacity  = bgOpacity;
    bgImage.style.display  = 'block';
  }
}

// ── Transition helpers ────────────────────────────────────────────────────────
function capturePrev() {
  if (!ctxP || !cvPrev) return;
  ctxP.clearRect(0, 0, cvPrev.width, cvPrev.height);
  ctxP.drawImage(cvCurr, 0, 0);
}

function startTransition(type, duration) {
  transition = { active: true, type, duration, start: performance.now(), progress: 0 };
  requestAnimationFrame(animLoop);
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function animLoop(ts) {
  if (!transition.active) return;
  const elapsed      = ts - transition.start;
  transition.progress = Math.min(1, elapsed / Math.max(1, transition.duration));
  const p = easeOutCubic(transition.progress);

  applyTransitionFrame(transition.type, p);

  if (transition.progress < 1) {
    requestAnimationFrame(animLoop);
  } else {
    transition.active = false;
    if (ctxP && cvPrev) ctxP.clearRect(0, 0, cvPrev.width, cvPrev.height);
  }
}

function applyTransitionFrame(type, p) {
  if (!ctxC || !cvCurr) return;
  const W = cvCurr.width, H = cvCurr.height;

  switch (type) {
    case 'crossfade': {
      ctxC.clearRect(0, 0, W, H);
      drawFrame(ctxC);
      ctxC.save();
      ctxC.globalAlpha = 1 - p;
      ctxC.drawImage(cvPrev, 0, 0);
      ctxC.restore();
      break;
    }
    case 'slide_left': {
      const offset = Math.round(p * W);
      ctxC.clearRect(0, 0, W, H);
      ctxC.drawImage(cvPrev, -offset, 0);
      ctxC.save();
      ctxC.beginPath();
      ctxC.rect(W - offset, 0, offset, H);
      ctxC.clip();
      drawFrame(ctxC);
      ctxC.restore();
      break;
    }
    case 'zoom_in': {
      ctxC.clearRect(0, 0, W, H);
      ctxC.save();
      ctxC.globalAlpha = 1 - p;
      const sc = 1 + p * 0.12;
      ctxC.translate(W / 2, H / 2);
      ctxC.scale(sc, sc);
      ctxC.translate(-W / 2, -H / 2);
      ctxC.drawImage(cvPrev, 0, 0);
      ctxC.restore();
      ctxC.save();
      ctxC.globalAlpha = p;
      drawFrame(ctxC);
      ctxC.restore();
      break;
    }
    case 'fade':
    default: {
      ctxC.clearRect(0, 0, W, H);
      ctxC.save();
      ctxC.globalAlpha = 1 - p;
      ctxC.drawImage(cvPrev, 0, 0);
      ctxC.restore();
      ctxC.save();
      ctxC.globalAlpha = p;
      drawFrame(ctxC);
      ctxC.restore();
      break;
    }
  }
}

// ── Render current frame (no transition) ─────────────────────────────────────
function renderCurrent() {
  if (!ctxC || !cvCurr) return;
  if (transition.active) return; // animLoop handles it
  ctxC.clearRect(0, 0, cvCurr.width, cvCurr.height);
  drawFrame(ctxC);
}

// ── Main draw function ────────────────────────────────────────────────────────
function drawFrame(ctx) {
  if (!ctx) return;
  const W = ctx.canvas.width  || window.innerWidth;
  const H = ctx.canvas.height || window.innerHeight;
  const s = state.settings;

  const bgType = s.bg_type || 'color';

  // Projector-off mode
  if (state.projOff) {
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#333';
    ctx.font = 'bold 28px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('PROJECTOR OFF', W / 2, H / 2);
    return;
  }

  // Background
  if (bgType === 'transparent') {
    ctx.clearRect(0, 0, W, H);
  } else if (bgType === 'gradient') {
    // Support both new (bg_grad_c1/c2/dir) and legacy (bg_color/bg_gradient_end) format
    const c1  = s.bg_grad_c1 || s.bg_color        || '#000033';
    const c2  = s.bg_grad_c2 || s.bg_gradient_end || '#000000';
    const dir = s.bg_grad_dir || 'Sus→Jos';
    let grad;
    if (dir === 'Stânga→Dreapta' || dir === 'left') {
      grad = ctx.createLinearGradient(0, 0, W, 0);
    } else if (dir === 'Diagonal' || dir === 'diagonal') {
      grad = ctx.createLinearGradient(0, 0, W, H);
    } else if (dir === 'Radial' || dir === 'radial') {
      grad = ctx.createRadialGradient(
        W / 2, H / 2, 0,
        W / 2, H / 2, Math.max(W, H) / 2);
    } else {
      // 'Sus→Jos' (top-to-bottom) default
      grad = ctx.createLinearGradient(0, 0, 0, H);
    }
    grad.addColorStop(0, c1);
    grad.addColorStop(1, c2);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);
  } else if (bgType === 'color') {
    ctx.fillStyle = s.bg_color || '#000000';
    ctx.fillRect(0, 0, W, H);
  } else if (bgType === 'animated_gradient') {
    renderAnimatedGradient(ctx, W, H, s);
  } else {
    // Image / video / camera — DOM elements handle it; canvas is transparent overlay
    ctx.clearRect(0, 0, W, H);
  }

  // Black screen
  if (state.isBlack) {
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, W, H);
    drawOverlays(ctx, W, H);
    return;
  }

  // Text (normal or dual-language)
  if (dualState.active) {
    drawDualText();
  } else if (state.text && state.text.trim().length > 0) {
    drawText(state.text, 1, 0, 0);
  }

  // Bible reference (bottom-right when source is 'bible')
  if (s.source === 'bible' || state.metadata?.source === 'bible') {
    const ref = state.metadata?.reference
              || s.bible_reference
              || '';
    if (ref) drawReference(ref, s, ctx, W, H);
  }

  drawOverlays(ctx, W, H);
}

// ── Smart word-wrap: balanced, no single-word lines, no mid-hyphen breaks ────
function smartWordWrap(rawLine, maxW, ctx) {
  if (!rawLine || !rawLine.trim()) return [rawLine || ''];

  // Tokenise — each \S+ run (including hyphens) is ONE atomic token
  const tokens = rawLine.match(/\S+/g) || [];
  if (tokens.length <= 1) return [rawLine];

  const full = tokens.join(' ');
  if (ctx.measureText(full).width <= maxW) return [full];

  let bestSplit = null;
  let bestScore = Infinity;

  for (let i = 1; i < tokens.length; i++) {
    const l1 = tokens.slice(0, i).join(' ');
    const l2 = tokens.slice(i).join(' ');
    const w1 = ctx.measureText(l1).width;
    if (w1 > maxW) continue;

    const w2 = ctx.measureText(l2).width;
    let penalty = 0;

    // Heavy penalty for single-word lines
    if (i === 1) penalty += 2000;
    if (tokens.length - i === 1) penalty += 2000;
    if (w2 > maxW) penalty += 1000;

    // Bonus for punctuation break
    const lastTok = tokens[i - 1];
    if (lastTok.endsWith(',')) penalty -= 800;
    else if (lastTok.endsWith(';')) penalty -= 600;
    else if (lastTok.endsWith(':')) penalty -= 400;

    const score = Math.abs(w1 - w2) + penalty;
    if (score < bestScore) { bestScore = score; bestSplit = i; }
  }

  if (bestSplit === null) bestSplit = Math.max(1, Math.floor(tokens.length / 2));

  const l1 = tokens.slice(0, bestSplit).join(' ');
  const l2 = tokens.slice(bestSplit).join(' ');
  const result = [l1];
  if (ctx.measureText(l2).width > maxW) {
    result.push(...smartWordWrap(l2, maxW, ctx));
  } else {
    result.push(l2);
  }
  return result;
}

// ── Dual-language state ───────────────────────────────────────────────────────
let dualState = {
  active:     false,
  original:   '',
  translated: '',
  layout:     {},
};

// ── Draw dual-language view ───────────────────────────────────────────────────
function drawDualText() {
  if (!dualState.active || !ctxC || !cvCurr) return;

  const W = cvCurr.width  || window.innerWidth;
  const H = cvCurr.height || window.innerHeight;
  const s = state.settings;
  const l = dualState.layout;

  const origZone = l.original || {
    x: 0.02, y: 0.05, width: 0.46, height: 0.90,
    font_size: parseInt(s.font_size || 60),
    color: s.text_color || '#ffffff',
    align: 'center', padding: 20,
  };
  const transZone = l.translated || {
    x: 0.52, y: 0.05, width: 0.46, height: 0.90,
    font_size: Math.floor(parseInt(s.font_size || 60) * 0.6),
    color: '#cccccc',
    align: 'center', padding: 20,
  };

  // Vertical separator
  ctxC.save();
  ctxC.strokeStyle = 'rgba(255,255,255,0.2)';
  ctxC.lineWidth   = 1;
  ctxC.setLineDash([8, 4]);
  ctxC.beginPath();
  ctxC.moveTo(W / 2, H * 0.05);
  ctxC.lineTo(W / 2, H * 0.95);
  ctxC.stroke();
  ctxC.setLineDash([]);
  ctxC.restore();

  drawTextInZone(dualState.original,   origZone,  W, H, s);
  drawTextInZone(dualState.translated, transZone, W, H, s);
}

function drawTextInZone(text, zone, W, H, s) {
  if (!text || !zone || !ctxC) return;

  const zx  = zone.x * W;
  const zy  = zone.y * H;
  const zw  = zone.width  * W;
  const zh  = zone.height * H;
  const pad = zone.padding || 20;

  const family = s.font_family || 'Arial';
  const bold   = zone.bold !== undefined ? zone.bold : s.font_bold === 'true';
  const shadow = s.text_shadow !== 'false';
  const outW   = parseInt(s.outline_width || 0);
  const outC   = s.outline_color || '#000';
  const color  = zone.color || s.text_color || '#ffffff';
  const align  = zone.align || 'center';

  let currentSize = zone.font_size || parseInt(s.font_size || 48);
  ctxC.font = `${bold ? 'bold ' : ''}${currentSize}px "${family}"`;

  const maxW = zw - pad * 2;
  let lines = [];
  text.split('\n').forEach(rawLine => {
    if (!rawLine.trim()) { lines.push(''); return; }
    lines.push(...smartWordWrap(rawLine, maxW, ctxC));
  });

  let lineH  = currentSize * 1.35;
  let totalH = lineH * lines.length;
  while (totalH > zh - pad * 2 && currentSize > 12) {
    currentSize -= 2;
    ctxC.font = `${bold ? 'bold ' : ''}${currentSize}px "${family}"`;
    lineH  = currentSize * 1.35;
    totalH = lineH * lines.length;
  }

  let startY = zy + (zh - totalH) / 2 + currentSize * 0.85;

  ctxC.save();
  lines.forEach((line, i) => {
    if (!line) return;
    const lw = ctxC.measureText(line).width;
    let lx;
    if (align === 'left')       lx = zx + pad;
    else if (align === 'right') lx = zx + zw - pad - lw;
    else                        lx = zx + (zw - lw) / 2;

    const y = startY + i * lineH;

    if (outW > 0) {
      ctxC.shadowColor = 'transparent'; ctxC.shadowBlur = 0;
      ctxC.strokeStyle = outC; ctxC.lineWidth = outW * 2; ctxC.lineJoin = 'round';
      ctxC.strokeText(line, lx, y);
    }
    if (shadow) {
      ctxC.shadowColor = 'rgba(0,0,0,0.8)'; ctxC.shadowBlur = 8;
      ctxC.shadowOffsetX = 2; ctxC.shadowOffsetY = 2;
    }
    ctxC.fillStyle = color;
    ctxC.fillText(line, lx, y);
    ctxC.shadowColor = 'transparent'; ctxC.shadowBlur = 0;
    ctxC.shadowOffsetX = 0; ctxC.shadowOffsetY = 0;
  });
  ctxC.restore();
}

// ── Sacred word capitalization & uppercase processing ─────────────────────────
function processText(text, s) {
  if (!text) return text;

  // Full uppercase takes priority
  if (s.uppercase === 'true' || s.uppercase === true) {
    return text.toUpperCase();
  }

  // Capitalize / all-caps sacred words
  if (s.sacred_words_enabled === 'true' || s.sacred_words_enabled === true) {
    const sacredAllCaps = s.sacred_words_allcaps === 'true' || s.sacred_words_allcaps === true;
    const customWords   = (s.sacred_words || '')
      .split(',')
      .map(w => w.trim().toLowerCase())
      .filter(w => w.length > 0);

    const defaultSacred = [
      'jesus', 'isus', 'hristos', 'christ', 'dumnezeu', 'god',
      'lord', 'domnul', 'doamne', 'duhul', 'spirit', 'tatal',
      'father', 'fiul', 'son', 'sfant', 'holy', 'amen',
      'hallelujah', 'aleluia',
    ];

    const allSacred = [...new Set([...defaultSacred, ...customWords])];
    let processed = text;

    allSacred.forEach(word => {
      if (!word) return;
      const regex = new RegExp(`\\b${word}\\b`, 'gi');
      processed = processed.replace(regex, match =>
        sacredAllCaps
          ? match.toUpperCase()
          : match.charAt(0).toUpperCase() + match.slice(1)
      );
    });

    return processed;
  }

  return text;
}

// ── Draw text (word-wrap + auto font-size so text never overflows) ────────────
function drawText(text, opacity, dx, dy) {
  if (!text || opacity <= 0) return;
  if (!ctxC || !cvCurr) return;

  const s = state.settings;
  const w = cvCurr.width  || window.innerWidth;
  const h = cvCurr.height || window.innerHeight;

  const size      = parseInt(s.font_size || 48);
  const bold      = s.font_bold   === 'true' || s.font_bold   === true;
  const italic    = s.font_italic === 'true' || s.font_italic === true;
  const family    = s.font_family || 'Arial';
  const color     = s.text_color  || '#ffffff';
  const shadow    = s.text_shadow !== 'false';
  const outW      = parseInt(s.outline_width || 2);
  const outC      = s.outline_color || '#000000';
  const lsp       = parseFloat(s.line_spacing || 1.4);
  // margin: if < 2 treat as fraction of min dimension, else as raw pixels
  const rawMargin = parseFloat(s.margin || 0.06);
  const margin    = rawMargin < 2
    ? Math.round(Math.min(w, h) * rawMargin)
    : parseInt(rawMargin);
  const displayText = processText(text, s);

  ctxC.save();
  ctxC.globalAlpha = Math.max(0, Math.min(1, opacity));
  if (dx) ctxC.translate(dx, 0);
  if (dy) ctxC.translate(0, dy);

  const maxW = w - margin * 2;
  const maxH = h - margin * 2;

  // ── Shrink font until everything fits ──────────────────────────────────────
  let currentSize = size;
  let lines  = [];
  let lineH  = 0;
  let totalH = 0;

  while (currentSize >= 10) {
    const fontStr =
      `${italic ? 'italic ' : ''}${bold ? 'bold ' : ''}${currentSize}px "${family}"`;
    ctxC.font = fontStr;

    // ── Word-wrap each source line (smart balanced wrap) ───────────────────
    lines = [];
    displayText.split('\n').forEach(rawLine => {
      if (!rawLine.trim()) { lines.push(''); return; }
      const wrapped = smartWordWrap(rawLine, maxW, ctxC);
      wrapped.forEach(wl => {
        if (ctxC.measureText(wl).width <= maxW) {
          lines.push(wl);
        } else {
          // Char-split fallback for oversized single word
          let part = '';
          for (const ch of wl) {
            if (ctxC.measureText(part + ch).width > maxW) {
              if (part) lines.push(part);
              part = ch;
            } else {
              part += ch;
            }
          }
          if (part) lines.push(part);
        }
      });
    });

    lineH  = currentSize * lsp;
    totalH = lineH * lines.length;

    const fitsV    = totalH <= maxH;
    const maxLineW = lines.length
      ? Math.max(...lines.map(l => ctxC.measureText(l).width))
      : 0;
    const fitsH    = maxLineW <= maxW;

    if (fitsV && fitsH) break;
    currentSize -= 2;
  }

  console.log('[Display.js] drawText — size:', currentSize,
    'lines:', lines.length, 'bold:', bold, 'color:', color);

  // ── Vertical alignment ─────────────────────────────────────────────────────
  const valign = s.text_valign || s.valign || 'center';
  let startY;
  if (valign === 'top') {
    startY = margin + currentSize * 0.85;
  } else if (valign === 'bottom') {
    startY = h - margin - totalH + currentSize * 0.85;
  } else {
    startY = (h - totalH) / 2 + currentSize * 0.85;
  }

  // ── Horizontal alignment ───────────────────────────────────────────────────
  const align = s.text_align || 'center';
  ctxC.textAlign    = align === 'left' ? 'left' : align === 'right' ? 'right' : 'center';
  ctxC.textBaseline = 'alphabetic';
  const baseX = align === 'left' ? margin
              : align === 'right' ? w - margin
              : w / 2;

  // ── Text box background (FreeShow-style) ────────────────────────────────────
  if (s.text_box_enabled === true || s.text_box_enabled === 'true') {
    drawTextBox(lines, lineH, startY, ctxC, w, h, s, currentSize, align, baseX);
  }

  // ── Draw each line ─────────────────────────────────────────────────────────
  lines.forEach((line, i) => {
    if (!line) return;   // skip empty (blank-line spacers already accounted for in totalH)
    const y = startY + i * lineH;

    // Outline (drawn before shadow so shadow sits on top)
    if (outW > 0) {
      ctxC.shadowColor   = 'transparent';
      ctxC.shadowBlur    = 0;
      ctxC.shadowOffsetX = 0;
      ctxC.shadowOffsetY = 0;
      ctxC.strokeStyle   = outC;
      ctxC.lineWidth     = outW * 2;
      ctxC.lineJoin      = 'round';
      ctxC.strokeText(line, baseX, y);
    }

    // Shadow
    if (shadow) {
      ctxC.shadowColor   = 'rgba(0,0,0,0.85)';
      ctxC.shadowBlur    = 8;
      ctxC.shadowOffsetX = 3;
      ctxC.shadowOffsetY = 3;
    } else {
      ctxC.shadowColor   = 'transparent';
      ctxC.shadowBlur    = 0;
      ctxC.shadowOffsetX = 0;
      ctxC.shadowOffsetY = 0;
    }

    ctxC.fillStyle = color;
    ctxC.fillText(line, baseX, y);
  });

  ctxC.restore();
}

// ── Bible reference ───────────────────────────────────────────────────────────
function drawReference(ref, s, ctx, W, H) {
  if (!ref || !ref.trim()) return;

  const family   = s.font_family   || 'Arial';
  const refSize  = parseInt(s.ref_font_size || 24);
  const refColor = s.ref_color     || '#aaaaaa';
  const rawMargin = parseFloat(s.margin || 0.06);
  const margin   = rawMargin < 2
    ? Math.round(Math.min(W, H) * rawMargin)
    : parseInt(rawMargin);

  ctx.save();
  ctx.shadowColor   = 'rgba(0,0,0,0.8)';
  ctx.shadowBlur    = 6;
  ctx.shadowOffsetX = 2;
  ctx.shadowOffsetY = 2;

  const refZone = s.bible_ref_zone;
  if (refZone && typeof refZone === 'object') {
    // Positioned zone from theme layout
    const rx = refZone.x / 100 * W;
    const ry = refZone.y / 100 * H;
    const rw = refZone.w / 100 * W;
    const rh = refZone.h / 100 * H;
    ctx.font         = `${refSize}px "${family}"`;
    ctx.fillStyle    = refColor;
    ctx.textAlign    = 'right';
    ctx.textBaseline = 'middle';
    ctx.fillText(ref, rx + rw, ry + rh / 2);
  } else {
    // Default: bottom-right corner
    ctx.font         = `italic ${refSize}px "${family}"`;
    ctx.fillStyle    = refColor;
    ctx.textAlign    = 'right';
    ctx.textBaseline = 'bottom';
    ctx.fillText(ref, W - margin, H - margin);
  }

  ctx.restore();
}

// ── Overlays ──────────────────────────────────────────────────────────────────
function drawOverlays(ctx, W, H) {
  if (state.tickerActive && state.tickerText) drawTicker(ctx, W, H);
  if (state.clockActive)                      drawClock(ctx, W, H);
  if (state.timerActive)                      drawTimer(ctx, W, H);
  if (state.logoPath)                         drawLogo(ctx, W, H);
}

// ── Ticker slide-in / slide-out animations ────────────────────────────────────

function showTickerWithEffect(effect, duration) {
  const H    = cvCurr ? cvCurr.height : window.innerHeight;
  const barH = Math.round(H * 0.08);
  const finalY = H - barH;

  if (effect === 'instant' || effect === 'none') {
    tickerState.barY      = finalY;
    tickerState.barOpacity = 1.0;
    tickerState.animating = false;
    return;
  }

  if (effect === 'fade') {
    tickerState.barY      = finalY;
    tickerState.barOpacity = 0;
    tickerState.animating = true;
    tickerState.slideDir  = 'in';
    tickerState.animStart = performance.now();
    tickerState.animDur   = duration;
    tickerState.onDone    = null;
    _tickerAnimLoop(performance.now());
    return;
  }

  // Default: slide_up
  tickerState.barY      = H;           // start below screen
  tickerState.targetY   = finalY;
  tickerState.barOpacity = 1.0;
  tickerState.animating = true;
  tickerState.slideDir  = 'in';
  tickerState.animStart = performance.now();
  tickerState.animDur   = duration;
  tickerState.onDone    = null;
  _tickerAnimLoop(performance.now());
}

function hideTickerWithEffect(effect, duration) {
  const H    = cvCurr ? cvCurr.height : window.innerHeight;

  if (effect === 'instant' || effect === 'none') {
    state.tickerActive    = false;
    state.tickerText      = '';
    tickerState.barY      = null;
    tickerState.animating = false;
    renderCurrent();
    return;
  }

  if (effect === 'fade') {
    tickerState.animating = true;
    tickerState.slideDir  = 'out';
    tickerState.animStart = performance.now();
    tickerState.animDur   = duration;
    tickerState.onDone    = () => {
      state.tickerActive = false;
      state.tickerText   = '';
      tickerState.barY   = null;
      tickerState.animating = false;
    };
    _tickerAnimLoop(performance.now());
    return;
  }

  // Default: slide_down
  tickerState.targetY   = H;           // slide down off screen
  tickerState.animating = true;
  tickerState.slideDir  = 'out';
  tickerState.animStart = performance.now();
  tickerState.animDur   = duration;
  tickerState.onDone    = () => {
    state.tickerActive = false;
    state.tickerText   = '';
    tickerState.barY   = null;
    tickerState.animating = false;
  };
  _tickerAnimLoop(performance.now());
}

function _tickerAnimLoop(ts) {
  if (!tickerState.animating) return;

  const elapsed  = ts - tickerState.animStart;
  const progress = Math.min(1, elapsed / Math.max(1, tickerState.animDur));
  const p        = easeOutCubic(progress);

  const H    = cvCurr ? cvCurr.height : window.innerHeight;
  const barH = Math.round(H * 0.08);
  const finalY = H - barH;

  if (tickerState.slideDir === 'in') {
    if (tickerState.targetY !== null) {
      // slide up: from H to finalY
      tickerState.barY = H + (finalY - H) * p;
    } else {
      // fade in
      tickerState.barOpacity = p;
      tickerState.barY = finalY;
    }
  } else {
    if (tickerState.targetY !== null) {
      // slide down: from barY to H
      const startY = tickerState.barY || finalY;
      tickerState.barY = finalY + (H - finalY) * p;
    } else {
      // fade out
      tickerState.barOpacity = 1 - p;
      tickerState.barY = finalY;
    }
  }

  if (progress < 1) {
    requestAnimationFrame(_tickerAnimLoop);
  } else {
    tickerState.animating = false;
    if (tickerState.onDone) {
      tickerState.onDone();
      tickerState.onDone = null;
    }
    if (tickerState.slideDir === 'in') {
      tickerState.barY     = finalY;
      tickerState.targetY  = null;
    }
  }
}

function drawTicker(ctx, W, H) {
  const ts   = tickerSettings;
  const barH = parseInt(ts.bar_height) || Math.round(H * 0.08);
  const pos  = ts.position || 'bottom';

  // Y: use animation state if active, otherwise snap to final position
  const finalY     = pos === 'top' ? 0 : H - barH;
  const y          = (tickerState.barY !== null) ? Math.round(tickerState.barY) : finalY;
  const bgCol      = ts.bg_color   || 'rgba(0,0,0,0.75)';
  const txtCol     = ts.text_color || '#ffdd44';
  const savedAlpha = ctx.globalAlpha;
  ctx.globalAlpha  = tickerState.barOpacity !== undefined ? tickerState.barOpacity : 1.0;

  // Bar background
  ctx.fillStyle = bgCol;
  ctx.fillRect(0, y, W, barH);

  // Accent line (top edge for bottom bar, bottom edge for top bar)
  ctx.save();
  ctx.strokeStyle = '#cba6f7';
  ctx.lineWidth   = 2;
  ctx.beginPath();
  const lineY = pos === 'top' ? y + barH : y;
  ctx.moveTo(0, lineY);
  ctx.lineTo(W, lineY);
  ctx.stroke();
  ctx.restore();

  // Text
  const fontSize   = parseInt(ts.font_size) || Math.round(barH * 0.55);
  const fontFamily = ts.font_family || 'Arial, sans-serif';
  ctx.font         = `bold ${fontSize}px "${fontFamily}"`;
  ctx.fillStyle    = txtCol;
  ctx.textBaseline = 'middle';
  ctx.textAlign    = 'left';

  ctx.save();
  ctx.shadowColor = 'rgba(0,0,0,0.5)';
  ctx.shadowBlur  = 4;
  ctx.beginPath();
  ctx.rect(0, y, W, barH);
  ctx.clip();
  ctx.fillText(state.tickerText, tickerX, y + barH / 2);
  ctx.restore();

  ctx.globalAlpha = savedAlpha;
}

function drawClock(ctx, W, H) {
  const clk = state.settings.clock || {};
  const s   = state.settings;

  const fontSize   = parseInt(clk.font_size   || s.clock_font_size   || Math.round(H * 0.035));
  const fontFamily = clk.font_family           || s.clock_font_family || 'Consolas, monospace';
  const color      = clk.color                 || s.clock_color       || '#ffffff';
  const position   = clk.position              || s.clock_position    || 'top_right';
  const bgEnabled  = clk.bg_enabled === true   || clk.bg_enabled === 'true'
                  || s.clock_bg_enabled === 'true';
  const bgColor    = clk.bg_color              || s.clock_bg_color    || 'rgba(0,0,0,0.5)';

  // Derive show_seconds / format_24h from the settings combo
  const clockFmt   = clk.clock_format || s.clock_format || 'HH:MM:SS';
  const format24   = clk.format_24h   !== false && clockFmt !== '12h';
  const showSecs   = clk.show_seconds !== false && (clockFmt === 'HH:MM:SS' || clk.show_seconds === true);

  const now = new Date();
  let timeStr;
  if (format24) {
    const h   = String(now.getHours()).padStart(2, '0');
    const m   = String(now.getMinutes()).padStart(2, '0');
    const sec = String(now.getSeconds()).padStart(2, '0');
    timeStr   = showSecs ? `${h}:${m}:${sec}` : `${h}:${m}`;
  } else {
    timeStr = now.toLocaleTimeString('en-US', {
      hour12:  true,
      hour:    '2-digit',
      minute:  '2-digit',
      second:  showSecs ? '2-digit' : undefined,
    });
  }

  ctx.save();
  ctx.font = `bold ${fontSize}px ${fontFamily}`;
  const textW = ctx.measureText(timeStr).width;
  const pad   = 10;

  let x, y;
  if      (position === 'top_left')      { x = pad;                   y = pad + fontSize; }
  else if (position === 'top_center')    { x = (W - textW) / 2;       y = pad + fontSize; }
  else if (position === 'bottom_right')  { x = W - textW - pad;       y = H - pad;        }
  else if (position === 'bottom_left')   { x = pad;                   y = H - pad;        }
  else if (position === 'bottom_center') { x = (W - textW) / 2;       y = H - pad;        }
  else                                   { x = W - textW - pad;       y = pad + fontSize; }  // top_right default

  if (bgEnabled) {
    ctx.fillStyle = bgColor;
    ctx.fillRect(x - pad / 2, y - fontSize - pad / 2, textW + pad, fontSize + pad);
  }

  ctx.shadowColor   = 'rgba(0,0,0,0.8)';
  ctx.shadowBlur    = 6;
  ctx.shadowOffsetX = 2;
  ctx.shadowOffsetY = 2;
  ctx.fillStyle     = color;
  ctx.textBaseline  = 'alphabetic';
  ctx.textAlign     = 'left';
  ctx.fillText(timeStr, x, y);
  ctx.restore();
}

function drawTimer(ctx, W, H) {
  if (!state.timerEnd) return;
  const remaining = Math.max(0, Math.ceil((state.timerEnd - Date.now()) / 1000));
  if (remaining === 0) { state.timerActive = false; return; }
  const mins  = String(Math.floor(remaining / 60)).padStart(2, '0');
  const secs  = String(remaining % 60).padStart(2, '0');
  const label = `${mins}:${secs}`;
  const fSize = Math.round(H * 0.06);
  const pad   = Math.round(H * 0.015);
  ctx.font         = `bold ${fSize}px "Courier New", monospace`;
  ctx.textBaseline = 'top';
  ctx.textAlign    = 'left';
  ctx.fillStyle    = 'rgba(0,0,0,0.5)';
  ctx.fillText(label, pad + 1, pad + 1);
  ctx.fillStyle    = '#00ff88';
  ctx.fillText(label, pad, pad);
}

function drawLogo(ctx, W, H) {
  const img = logoCache[state.logoPath];
  if (!img) {
    const lp  = state.logoPath;
    const i2  = new Image();
    i2.onload  = () => { logoCache[lp] = i2; renderCurrent(); };
    i2.onerror = () => { logoCache[lp] = null; };
    i2.src = lp.startsWith('file://') ? lp : `file://${lp}`;
    return;
  }
  const maxW  = Math.round(W * 0.15);
  const maxH  = Math.round(H * 0.12);
  const scale = Math.min(maxW / img.width, maxH / img.height);
  const dw    = img.width  * scale;
  const dh    = img.height * scale;
  const pad   = Math.round(H * 0.02);
  ctx.globalAlpha = 0.85;
  ctx.drawImage(img, pad, pad, dw, dh);
  ctx.globalAlpha = 1;
}

// ── Rounded rect helper ───────────────────────────────────────────────────────
function roundRect(ctx, x, y, w, h, r) {
  r = Math.min(r, Math.min(w, h) / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

// ── Text box background (FreeShow-style) ──────────────────────────────────────
function drawTextBox(lines, lineH, startY, ctx, W, H, s, currentSize, align, baseX) {
  const boxColor   = s.text_box_color   || '#000000';
  const opacity    = parseFloat(s.text_box_opacity  ?? 0.6);
  const padH       = parseInt(s.text_box_padding_h  ?? 20);
  const padV       = parseInt(s.text_box_padding_v  ?? 12);
  const radius     = parseInt(s.text_box_radius     ?? 8);
  const fit        = s.text_box_fit     || 'per_line';

  // Parse color to rgba
  const tmp = document.createElement('canvas').getContext('2d');
  tmp.fillStyle = boxColor;
  const parsed = tmp.fillStyle;   // normalised hex string

  ctx.save();
  ctx.globalAlpha = opacity;
  ctx.fillStyle   = parsed;

  if (fit === 'full_block') {
    // Single rectangle enclosing all lines
    let maxLineW = 0;
    ctx.font = `${currentSize}px sans-serif`;  // approximate — already measured
    lines.forEach(line => {
      if (!line) return;
      const lw = ctx.measureText(line).width;
      if (lw > maxLineW) maxLineW = lw;
    });
    const bx = (align === 'left'  ? baseX - padH
              : align === 'right' ? baseX - maxLineW - padH
              : baseX - maxLineW / 2 - padH);
    const by = startY - currentSize * 0.85 - padV;
    const bw = maxLineW + padH * 2;
    const bh = lineH * lines.length + padV * 2;
    roundRect(ctx, bx, by, bw, bh, radius);
    ctx.fill();
  } else if (fit === 'full_width') {
    lines.forEach((line, i) => {
      if (!line) return;
      const by = startY + i * lineH - currentSize * 0.85 - padV;
      const bh = currentSize + padV * 2;
      roundRect(ctx, 0, by, W, bh, 0);
      ctx.fill();
    });
  } else {
    // 'per_line' (default): individual rect per line sized to text width
    lines.forEach((line, i) => {
      if (!line) return;
      const lw  = ctx.measureText(line).width;
      const bx  = (align === 'left'  ? baseX - padH
                 : align === 'right' ? baseX - lw - padH
                 : baseX - lw / 2 - padH);
      const by  = startY + i * lineH - currentSize * 0.85 - padV;
      const bw  = lw + padH * 2;
      const bh  = currentSize + padV * 2;
      roundRect(ctx, bx, by, bw, bh, radius);
      ctx.fill();
    });
  }
  ctx.restore();
}

// ── Animated gradient background ──────────────────────────────────────────────
function renderAnimatedGradient(ctx, W, H, s) {
  const colors = (s.anim_grad_colors || gradientAnim.colors);
  const speed  = parseFloat(s.anim_grad_speed || gradientAnim.speed || 0.5);
  const t      = gradientAnim.time * speed;

  // Black base
  ctx.fillStyle = '#000000';
  ctx.fillRect(0, 0, W, H);

  ctx.save();
  ctx.globalCompositeOperation = 'screen';

  colors.forEach((color, idx) => {
    const phase  = (t + idx * (Math.PI * 2 / colors.length));
    const cx     = W * (0.3 + 0.4 * Math.sin(phase * 0.7));
    const cy     = H * (0.3 + 0.4 * Math.cos(phase * 0.5));
    const radius = Math.max(W, H) * (0.4 + 0.2 * Math.sin(phase * 1.3));

    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
    grad.addColorStop(0, color);
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);
  });

  ctx.restore();
}

// ── Main animation loop ───────────────────────────────────────────────────────
function mainLoop(ts) {
  const dt = ts - lastTickTs;
  lastTickTs = ts;

  let needRedraw = false;

  // Advance animated gradient time
  if ((state.settings.bg_type || '') === 'animated_gradient') {
    gradientAnim.time += dt / 1000;
    needRedraw = true;
  }

  if (state.tickerActive && state.tickerText && cvCurr) {
    // speed 1–10; speed=5 → ~300 px/sec, speed=3 → ~180 px/sec
    const spd      = parseFloat(tickerSettings.speed || state.settings.ticker_speed || 3);
    const pxPerSec = spd * 60;
    tickerX -= pxPerSec * dt / 1000;
    const textW = (ctxC ? ctxC.measureText(state.tickerText).width : 0) || cvCurr.width;
    if (tickerX < -textW - 50) tickerX = cvCurr.width + 50;
    needRedraw = true;
  }

  if (state.clockActive || state.timerActive) needRedraw = true;

  if (needRedraw && !transition.active) renderCurrent();

  requestAnimationFrame(mainLoop);
}
