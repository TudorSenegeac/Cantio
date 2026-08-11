/**
 * Cantio Electron Display – display.js
 * Renderer process: receives IPC 'render' events and paints to canvas.
 */

'use strict';

const { ipcRenderer } = require('electron');

console.log('[Display.js] Script încărcat!');

// Signals main.js to start fade-in once the first frame is rendered
let _firstRenderDone = false;
function _signalFirstRender() {
  if (_firstRenderDone) return;
  _firstRenderDone = true;
  try { ipcRenderer.send('frame_rendered'); } catch {}
}

// ── Canvas setup ─────────────────────────────────────────────────────────────
const cvPrev  = document.getElementById('canvas-prev');
const cvCurr  = document.getElementById('canvas-curr');
const cvBg    = document.getElementById('canvas-bg');
const cvBg2   = document.getElementById('canvas-bg2');
const bgVideo = document.getElementById('bg-video');
const bgImage = document.getElementById('bg-image');
const ctxBg   = cvBg  ? cvBg.getContext('2d')  : null;
const ctxBg2  = cvBg2 ? cvBg2.getContext('2d') : null;

if (!cvPrev || !cvCurr) {
  console.error('[Display.js] ❌ Canvas elements NOT FOUND în DOM!');
}

const ctxP = cvPrev ? cvPrev.getContext('2d') : null;
const ctxC = cvCurr ? cvCurr.getContext('2d') : null;

if (!ctxC) console.error('[Display.js] ❌ CTX NULL!');

// Offscreen transition buffers — hold pre-rendered OLD and NEW frames so the
// animation composites bitmaps (drawImage) instead of re-running drawFrame()
// each tick (which would clear the canvas on transparent / camera / video bg).
const bufOld    = document.createElement('canvas');
const bufNew    = document.createElement('canvas');
const bufOldCtx = bufOld.getContext('2d');
const bufNewCtx = bufNew.getContext('2d');

// Preview mode (?preview=1): render at a FIXED projector resolution and let CSS
// (width/height:100%) scale the canvas down to the embedded window. This makes
// the preview a faithful, proportionally-identical copy of the live output —
// independent of the small window size (no font-shrink discrepancy).
const IS_PREVIEW = new URLSearchParams(location.search).get('preview') === '1';
const PREVIEW_W = 1920, PREVIEW_H = 1080;

// ── Resize ────────────────────────────────────────────────────────────────────
function resize() {
  if (!cvPrev || !cvCurr) return;
  const W = IS_PREVIEW ? PREVIEW_W : window.innerWidth;
  const H = IS_PREVIEW ? PREVIEW_H : window.innerHeight;
  cvPrev.width  = cvCurr.width  = W;
  cvPrev.height = cvCurr.height = H;
  if (cvBg)  { cvBg.width  = W; cvBg.height  = H; }
  if (cvBg2) { cvBg2.width = W; cvBg2.height = H; }
  console.log('[Display.js] Resize:', cvCurr.width, 'x', cvCurr.height,
              IS_PREVIEW ? '(preview, CSS-scaled)' : '');
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
  presMode:     false,   // true → show presentation slide via JSON
  presSlide:    null,    // current presentation slide data dict
  bgDoc:        null,    // active custom background (bg-engine JSON), or null
  dim:          { black: 0, text: 0, logo: 0, bg: 0 },  // per-layer hide (0..1)
};

// ── Custom animated background (bg-engine) ──────────────────────────────────
let _bgStart = 0;
let _bgIntroUntil = 0;   // play layer entrance animations until this timestamp

function _maxIntroMs(doc) {
  let m = 0;
  (doc.layers || []).forEach((L, i) => {
    const e = L.entrance || {};
    if (e.type && e.type !== 'none') {
      const seq = doc.intro_sequence ? i * (doc.intro_stagger || 350) : 0;
      m = Math.max(m, seq + (e.delay || 0) + (e.duration || 600));
    }
  });
  return m;
}

function bgEngineLoop(ts) {
  if (state.bgDoc && ctxBg && cvBg && typeof BgEngine !== 'undefined') {
    if (!_bgStart) _bgStart = ts;
    const t = ts - _bgStart;
    // Feed the current lyrics into any lyrics layer
    if (state.lines && state.lines.length) {
      state.bgDoc._lyrics = {
        lines: state.lines,
        index: Math.floor((state.lines.length - 1) / 2),
      };
    } else {
      state.bgDoc._lyrics = null;
    }
    // Play the slide's entrance animations for the first _maxIntroMs.
    const opts = (ts < _bgIntroUntil) ? { intro: t } : 1;
    try { BgEngine.render(ctxBg, cvBg.width, cvBg.height, state.bgDoc, t, opts); }
    catch (e) { /* keep looping */ }
  }
  _dynamicTick();
  requestAnimationFrame(bgEngineLoop);
}
requestAnimationFrame(bgEngineLoop);

// ── Dynamic presentation: audio playback + Web Audio analyser + auto-advance ──
// A self-contained mode: the audio is the clock. Each frame we read the track's
// energy bands → BgEngine.setAudio (reactive backgrounds), pick the current
// slide from audio.currentTime, and drive word-by-word reveal within the slide.
let _dyn = null;          // { slides, times, reveal, idx }
let _audioEl = null, _audioCtx = null, _analyser = null, _freqData = null;
let _binAudio = null;     // Audio Bin (background music)
function _ensureBinAudio() {
  if (!_binAudio) { _binAudio = document.createElement('audio'); document.body.appendChild(_binAudio); }
  return _binAudio;
}

function _ensureAudioGraph() {
  if (!_audioEl) {
    _audioEl = document.createElement('audio');
    _audioEl.crossOrigin = 'anonymous';
    document.body.appendChild(_audioEl);
  }
  if (!_audioCtx) {
    try {
      _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const srcNode = _audioCtx.createMediaElementSource(_audioEl);
      _analyser = _audioCtx.createAnalyser();
      _analyser.fftSize = 256;
      _analyser.smoothingTimeConstant = 0.8;
      _freqData = new Uint8Array(_analyser.frequencyBinCount);
      srcNode.connect(_analyser);
      _analyser.connect(_audioCtx.destination);
    } catch (e) { console.warn('[Dynamic] audio graph failed:', e); }
  }
}

function _bandAvg(data, from, to) {
  let s = 0, n = 0;
  for (let i = from; i < to && i < data.length; i++) { s += data[i]; n++; }
  return n ? (s / n) / 255 : 0;
}

function _dynamicTick() {
  if (!_dyn || !_audioEl) return;
  // 1) Audio energy → reactive backgrounds + whole-frame distortion on the beat
  if (_analyser && _freqData) {
    _analyser.getByteFrequencyData(_freqData);
    const N = _freqData.length;
    const bass = _bandAvg(_freqData, 0, Math.floor(N * 0.12));
    const mid = _bandAvg(_freqData, Math.floor(N * 0.12), Math.floor(N * 0.45));
    const treble = _bandAvg(_freqData, Math.floor(N * 0.45), N);
    const level = (bass * 1.3 + mid + treble * 0.7) / 3;
    BgEngine.setAudio({ level, bass, mid, treble });
    // Background "breathes"/distorts on bass; flashes brighter on peaks.
    if (cvBg) {
      cvBg.style.transformOrigin = '50% 50%';
      cvBg.style.transform = `scale(${(1 + bass * 0.05).toFixed(4)})`;
      cvBg.style.filter = bass > 0.62 ? `brightness(${(1 + (bass - 0.62) * 0.7).toFixed(3)}) contrast(${(1 + (bass - 0.62) * 0.5).toFixed(3)})` : '';
    }
  }
  // 2) Current slide from the audio clock
  const ct = _audioEl.currentTime || 0;
  const times = _dyn.times, slides = _dyn.slides;
  let idx = 0;
  for (let i = 0; i < times.length; i++) { if (ct >= times[i]) idx = i; else break; }
  if (idx !== _dyn.idx) {
    _dyn.idx = idx;
    const fx = (slides[idx] && slides[idx]._transition) || _dyn.transition || 'fade';
    setCustomBackground(slides[idx], fx);
    try { ipcRenderer.send('dynamic_slide', idx); } catch (e) {}
  }
  // 3) Word-by-word reveal within the current slide
  if (_dyn.reveal) {
    const start = times[idx] || 0;
    const end = (idx + 1 < times.length) ? times[idx + 1] : (_audioEl.duration || start + 5);
    const span = Math.max(0.3, (end - start) * 0.8);   // reveal over first 80% of slot
    BgEngine.setReveal(Math.max(0, Math.min(1, (ct - start) / span)));
  } else {
    BgEngine.setReveal(1);
  }
}

function startDynamic(msg) {
  const slides = Array.isArray(msg.slides) ? msg.slides : [];
  if (!slides.length) return;
  _ensureAudioGraph();
  // Load each slide's media (image/video layers) up front
  slides.forEach(loadDocMedia);
  _dyn = { slides, times: [], reveal: msg.reveal !== false,
           transition: msg.transition || 'fade', idx: -1 };
  const begin = () => {
    const dur = _audioEl.duration || (slides.length * 8);
    if (Array.isArray(msg.times) && msg.times.length === slides.length) {
      _dyn.times = msg.times.slice();                       // explicit times
    } else if (Array.isArray(msg.weights) && msg.weights.length === slides.length) {
      // Text-proportional timing: longer verses get more time than short ones.
      const total = msg.weights.reduce((a, b) => a + (b > 0 ? b : 1), 0) || 1;
      let acc = 0;
      _dyn.times = slides.map((_, i) => {
        const t = (acc / total) * dur;
        acc += (msg.weights[i] > 0 ? msg.weights[i] : 1);
        return t;
      });
    } else {
      const per = dur / slides.length;                      // even distribution
      _dyn.times = slides.map((_, i) => i * per);
    }
    _dyn.idx = -1;            // force first slide render on next tick
    if (_audioCtx && _audioCtx.state === 'suspended') _audioCtx.resume().catch(() => {});
    _audioEl.play().catch(e => console.warn('[Dynamic] play blocked:', e));
  };
  const src = msg.audio || '';
  _audioEl.src = /^(file|https?|data|blob):/i.test(src)
    ? src : ('file:///' + String(src).replace(/\\/g, '/'));
  if (_audioEl.readyState >= 1 && _audioEl.duration) begin();
  else _audioEl.addEventListener('loadedmetadata', begin, { once: true });
  _signalFirstRender();
}

function stopDynamic() {
  if (_audioEl) { try { _audioEl.pause(); } catch (e) {} _audioEl.src = ''; }
  _dyn = null;
  BgEngine.setReveal(1);
  BgEngine.setAudio({ level: 0, bass: 0, mid: 0, treble: 0 });
  if (cvBg) { cvBg.style.transform = ''; cvBg.style.filter = ''; }
}

// CSS "exit" state for the old-bg snapshot, per transition effect.
function _bgExitStyle(effect) {
  switch (effect) {
    case 'slide_left':  case 'reveal_left':  case 'push_left':  return { transform: 'translateX(-100%)' };
    case 'slide_right': case 'reveal_right': case 'push_right': return { transform: 'translateX(100%)' };
    case 'slide_up':    case 'reveal_up':    case 'push_up':    return { transform: 'translateY(-100%)' };
    case 'slide_down':  case 'reveal_down':  case 'push_down':  return { transform: 'translateY(100%)' };
    case 'zoom_in':     return { transform: 'scale(1.4)',  opacity: '0' };
    case 'zoom_out':    return { transform: 'scale(0.6)',  opacity: '0' };
    case 'wipe_left':   return { clipPath: 'inset(0 0 0 100%)' };
    case 'wipe_right':  return { clipPath: 'inset(0 100% 0 0)' };
    case 'wipe_up':     return { clipPath: 'inset(100% 0 0 0)' };
    case 'wipe_down':   return { clipPath: 'inset(0 0 100% 0)' };
    case 'iris_close':  return { clipPath: 'circle(0%)' };
    case 'iris_open':   return { clipPath: 'circle(0%)', opacity: '0' };
    case 'instant':     return { opacity: '0' };
    default:            return { opacity: '0' };   // fade / crossfade / unsupported
  }
}

// bg-engine never loads media itself — the host must create the <img>/<video>
// element and register it. The editor does this on file-pick; display.js must
// do it too, otherwise image/video layers show in the editor but NOT live or
// in the preview. Cached by layerId|src so re-pushing the same doc is cheap.
const _bgMediaCache = {};
function loadDocMedia(doc) {
  if (!doc || !Array.isArray(doc.layers) || typeof BgEngine === 'undefined') return;
  doc.layers.forEach((L) => {
    if (L.type !== 'image' && L.type !== 'video') return;
    const src = L.src || '';
    if (!src) return;
    const key = L.id + '|' + src;
    const cached = _bgMediaCache[key];
    if (cached) { BgEngine.registerMedia(L.id, cached, L.type); return; }
    const isVideo = L.type === 'video';
    const el = isVideo ? document.createElement('video') : new Image();
    if (isVideo) { el.loop = (L.loop !== false); el.muted = true; el.autoplay = true; el.playsInline = true; }
    el.onloadeddata = el.onload = () => BgEngine.registerMedia(L.id, el, L.type);
    // Raw file path → file:/// URL; http(s)/data/blob/file used as-is.
    el.src = /^(file|https?|data|blob):/i.test(src)
      ? src : ('file:///' + src.replace(/\\/g, '/'));
    if (isVideo) el.play().catch(() => {});
    _bgMediaCache[key] = el;
    BgEngine.registerMedia(L.id, el, L.type);
  });
}

// WYSIWYG thumbnail: render a bg-engine slide doc to a small offscreen canvas
// and return a PNG data-URL. Runs inside the ALREADY-running renderer (no new
// process); the detached canvas doesn't touch the visible output. Called from
// main.js via executeJavaScript for the operator's slide thumbnails.
window._renderThumb = function (doc, w, h) {
  try {
    if (typeof BgEngine === 'undefined' || !doc) return '';
    w = Math.max(16, w | 0); h = Math.max(9, h | 0);
    if (Array.isArray(doc.layers)) loadDocMedia(doc);   // best-effort media
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    BgEngine.render(c.getContext('2d'), w, h, doc, 0, 1);
    return c.toDataURL('image/png');
  } catch (e) { return ''; }
};

// Countdown sounds: a per-second "tick" (tickSound) played on every second, and an
// optional end sound (endSound) played once when the countdown reaches zero.
let _cdSoundTimers = [];
function _clearCountdownSounds() {
  _cdSoundTimers.forEach(h => { clearTimeout(h); clearInterval(h); });
  _cdSoundTimers = [];
}
function _playSnd(snd) {
  try {
    const src = /^(file|https?|data):/i.test(snd)
              ? snd : 'file:///' + String(snd).replace(/\\/g, '/');
    new Audio(src).play().catch(() => {});
  } catch (e) {}
}
function _scheduleCountdownSounds(doc) {
  _clearCountdownSounds();
  if (!doc || !Array.isArray(doc.layers)) return;
  for (const L of doc.layers) {
    if (L.type !== 'clock' || L.clockMode !== 'countdown') continue;
    const durSec = Math.max(0, (L.duration || 300));
    if (L.tickSound) {
      let n = 0;
      const iv = setInterval(() => {
        n++;
        if (n > durSec) { clearInterval(iv); return; }
        _playSnd(L.tickSound);
      }, 1000);
      _cdSoundTimers.push(iv);
    }
    if (L.endSound) {
      _cdSoundTimers.push(setTimeout(() => _playSnd(L.endSound), durSec * 1000));
    }
  }
}

function setCustomBackground(doc, transition) {
  loadDocMedia(doc);
  _scheduleCountdownSounds(doc);
  const switching = !!(state.bgDoc && doc && cvBg2 && ctxBg2);
  const dur = Math.max(120, parseInt(state.settings.transition_duration || 500, 10));
  const fx  = transition || state.settings.bg_transition || 'fade';

  if (switching) {
    // 1) Snapshot the OLD background onto cvBg2 (on top), reset its styles.
    ctxBg2.clearRect(0, 0, cvBg2.width, cvBg2.height);
    try { ctxBg2.drawImage(cvBg, 0, 0); } catch (e) {}
    cvBg2.style.transition = 'none';
    cvBg2.style.transform  = 'none';
    cvBg2.style.opacity    = '1';
    cvBg2.style.clipPath   = 'none';
    cvBg2.style.zIndex     = '0';
    cvBg2.style.display    = 'block';

    // 2) Swap to the NEW background underneath (renders immediately).
    state.bgDoc = doc; _bgStart = 0;
    _bgIntroUntil = performance.now() + 16 + _maxIntroMs(doc);
    cvBg.style.transition = 'none';
    cvBg.style.transform  = 'none';
    cvBg.style.opacity    = String(1 - (state.dim.bg || 0));
    cvBg.style.display     = 'block';

    // 3) Animate the OLD snapshot OUT with the chosen effect.
    requestAnimationFrame(() => {
      const ease = (fx === 'instant') ? 'linear' : 'cubic-bezier(.4,0,.2,1)';
      cvBg2.style.transition = `transform ${dur}ms ${ease}, opacity ${dur}ms ${ease}, clip-path ${dur}ms ${ease}`;
      const ex = _bgExitStyle(fx);
      if (ex.transform) cvBg2.style.transform = ex.transform;
      if (ex.opacity)   cvBg2.style.opacity   = ex.opacity;
      if (ex.clipPath)  cvBg2.style.clipPath  = ex.clipPath;
    });
    setTimeout(() => {
      cvBg2.style.display = 'none';
      cvBg2.style.transition = 'none';
      cvBg2.style.transform = 'none';
      cvBg2.style.clipPath = 'none';
      if (ctxBg2) ctxBg2.clearRect(0, 0, cvBg2.width, cvBg2.height);
    }, dur + 40);
  } else {
    state.bgDoc = doc || null;
    _bgStart = 0;
    _bgIntroUntil = state.bgDoc ? performance.now() + 16 + _maxIntroMs(state.bgDoc) : 0;
    if (cvBg) {
      cvBg.style.transition = 'opacity 0.4s ease';
      cvBg.style.display = state.bgDoc ? 'block' : 'none';
      const _o = state.bgDoc ? String(1 - (state.dim.bg || 0)) : '0';
      requestAnimationFrame(() => { cvBg.style.opacity = _o; });
    }
    if (!state.bgDoc && ctxBg && cvBg) ctxBg.clearRect(0, 0, cvBg.width, cvBg.height);
  }
  // Text canvases stay transparent so the background shows through behind lyrics.
  renderCurrent();
}

// Transition
let transition = { active: false, type: 'fade', duration: 400, start: 0, progress: 1 };
let _animRunning = false;   // ensures a single animLoop rAF chain at a time

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
      // Clear the bible reference too — it lives on settings (source/bible_reference)
      // and would otherwise stay on screen after the verse text is gone.
      if (state.settings) {
        state.settings.source         = '';
        state.settings.bible_reference = '';
      }
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
      _signalFirstRender();
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
      const _bgSigBefore = _bgSignature(state.settings);
      state.settings = { ...state.settings, ...incoming };
      const _bgSigAfter = _bgSignature(state.settings);
      applyBackground(state.settings);
      // Transition the background when it actually changes (e.g. switching to a
      // song with a different theme). Use the theme's configured transition so it
      // is settable from the Theme editor. Avoid transitioning on every settings
      // packet (those arrive on each slide) — only when the bg signature changed.
      if (_bgSigBefore !== _bgSigAfter && !transition.active) {
        capturePrev();
        const bgTType = state.settings.bg_transition
                      || state.settings.transition
                      || 'fade';
        const bgTDur  = parseInt(state.settings.bg_transition_duration
                      || state.settings.transition_duration
                      || 450, 10);
        if (bgTType === 'instant' || bgTType === 'none') {
          renderCurrent();
        } else {
          startTransition(bgTType, bgTDur);
        }
      } else {
        renderCurrent();
      }
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

    case 'show_web': {
      // Display an online page (e.g. a YouTube video) in a full-screen iframe.
      let url = _toEmbedUrl(msg.url || '');
      if (!url) break;
      let f = document.getElementById('web-frame');
      if (!f) {
        f = document.createElement('iframe');
        f.id = 'web-frame';
        f.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;'
                        + 'border:0;z-index:9999;background:#000;';
        f.setAttribute('allow', 'autoplay; encrypted-media; fullscreen; picture-in-picture');
        f.setAttribute('allowfullscreen', 'true');
        document.body.appendChild(f);
      }
      f.src = url;
      f.style.display = 'block';
      console.log('[Display.js] show_web:', url);
      break;
    }

    case 'hide_web': {
      const f = document.getElementById('web-frame');
      if (f) { f.src = 'about:blank'; f.style.display = 'none'; }
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

    // ── Presentation slide ─────────────────────────────────────────────────
    case 'show_presentation_slide': {
      capturePrev();
      state.isBlack  = false;
      state.projOff  = false;
      state.text     = '';
      state.lines    = [];
      state.presSlide = msg.slide || null;
      state.presMode  = true;

      const pTrans = msg.transition || (msg.slide && msg.slide.transition) || 'fade';
      const pDur   = parseInt(
        msg.transition_ms || (msg.slide && msg.slide.transition_ms) || 400, 10);

      if (pTrans === 'instant' || pTrans === 'none') {
        renderCurrent();
        _signalFirstRender();
      } else {
        startTransition(pTrans, pDur);
        // schedule animation entrance for elements
        if (msg.slide && msg.slide.elements) {
          _startPresAnimations(msg.slide.elements, pDur);
        }
      }
      break;
    }

    case 'clear_presentation': {
      capturePrev();
      state.presMode  = false;
      state.presSlide = null;
      startTransition('fade', 300);
      break;
    }

    case 'show_background': {
      // Custom animated background from the Fundal editor (bg-engine JSON)
      setCustomBackground(msg.background || null, msg.transition);
      _signalFirstRender();
      break;
    }

    case 'dim': {
      // Per-layer hide (output-layer control): target = black|text|logo|bg, 0..1
      const tgt = msg.target;
      if (tgt && state.dim[tgt] !== undefined) {
        state.dim[tgt] = Math.max(0, Math.min(1, parseFloat(msg.value) || 0));
        if (tgt === 'bg') {
          const o = String(1 - state.dim.bg);
          if (cvBg)  { cvBg.style.transition = 'opacity 0.25s ease';  cvBg.style.opacity = o; }
          if (cvBg2) { cvBg2.style.opacity = o; }
        } else {
          renderCurrent();
        }
      }
      break;
    }

    case 'manual_prep': { _manualPrep(msg.text || '', msg.transition || 'fade'); break; }
    case 'manual_set':  { _manualStep(parseFloat(msg.p) || 0); break; }
    case 'manual_end':  { _manualEnd(!!msg.commit); break; }

    case 'clear_background': {
      setCustomBackground(null);
      break;
    }

    // ── Dynamic presentation (audio-reactive) ─────────────────────────────────
    case 'dynamic_play':  { startDynamic(msg); break; }
    case 'dynamic_stop':  { stopDynamic(); break; }
    case 'audio_pause':   { if (_audioEl) _audioEl.pause(); break; }
    case 'audio_resume':  {
      if (_audioEl) {
        if (_audioCtx && _audioCtx.state === 'suspended') _audioCtx.resume().catch(() => {});
        _audioEl.play().catch(() => {});
      }
      break;
    }
    case 'audio_volume':  { if (_audioEl) _audioEl.volume = Math.max(0, Math.min(1, parseFloat(msg.value))); break; }

    // ── Audio Bin (background music, independent of presentations) ────────────
    case 'audio_bin_play': {
      const el = _ensureBinAudio();
      const src = msg.src || '';
      el.loop = !!msg.loop;
      el.src = /^(file|https?|data|blob):/i.test(src)
        ? src : ('file:///' + String(src).replace(/\\/g, '/'));
      el.play().catch(() => {});
      break;
    }
    case 'audio_bin_pause':  { if (_binAudio) _binAudio.pause(); break; }
    case 'audio_bin_resume': { if (_binAudio) _binAudio.play().catch(() => {}); break; }
    case 'audio_bin_stop':   { if (_binAudio) { _binAudio.pause(); _binAudio.src = ''; } break; }
    case 'audio_bin_volume': { if (_binAudio) _binAudio.volume = Math.max(0, Math.min(1, parseFloat(msg.value))); break; }
    case 'audio_seek':    {
      if (_audioEl && _audioEl.duration) _audioEl.currentTime = Math.max(0, Math.min(1, parseFloat(msg.p))) * _audioEl.duration;
      break;
    }

    default:
      console.warn('[Display.js] Tip mesaj necunoscut:', type);
  }
}

// ── Background ────────────────────────────────────────────────────────────────

// Signature of all background-relevant settings — used to detect bg changes.
function _toEmbedUrl(url) {
  // YouTube watch/short links → embed URL with autoplay so it plays on the wall.
  try {
    if (!url) return '';
    url = url.trim();
    const m = url.match(/(?:youtube\.com\/(?:watch\?v=|embed\/|live\/)|youtu\.be\/)([\w-]{11})/);
    if (m) return 'https://www.youtube.com/embed/' + m[1] + '?autoplay=1&rel=0&modestbranding=1';
    if (!/^https?:\/\//i.test(url)) url = 'https://' + url;
    return url;   // any other link loads as-is
  } catch (e) { return url; }
}

function _bgSignature(s) {
  if (!s) return '';
  return [s.bg_type, s.bg_color, s.bg_image, s.bg_grad_c1, s.bg_grad_c2,
          s.bg_grad_dir, s.bg_fundal_file, s.bg_transparent, s.bg_opacity].join('|');
}

// Last background actually loaded into the DOM. Used to avoid restarting a video
// or camera stream on every slide change — the text and the background are
// independent, so navigating text must NOT reload unchanged background media.
let _lastAppliedBgSig = null;

function applyBackground(s) {
  if (!s) return;

  // Skip the (expensive) media reload when the background is unchanged. Without
  // this, each show_text/settings packet on slide navigation would re-run
  // getUserMedia (camera) or reset video.src (video) — freezing the background.
  const _sig = _bgSignature(s);
  if (_sig === _lastAppliedBgSig) return;
  _lastAppliedBgSig = _sig;

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

  // ── Camera (plain or with gradient overlay) ─────────────────────────────────
  if (bgType === 'camera' || bgType === 'camera_gradient') {
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
    if (bgImage.src !== fixedPath) {
      bgImage.style.opacity = '0';            // fade in via CSS transition
      bgImage.onload = () => {
        renderCurrent(); _signalFirstRender();
        requestAnimationFrame(() => { bgImage.style.opacity = bgOpacity; });
      };
      bgImage.src    = fixedPath;
    }
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
  if (!ctxC || !cvCurr) return;
  const W = cvCurr.width, H = cvCurr.height;

  // Transitions composite ONLY the text/foreground canvas. The live background
  // (video / animated custom bg) keeps playing underneath and is never frozen
  // or hidden — so it never stutters or darkens during a slide change. For
  // colour/gradient backgrounds the bg lives on the text canvas anyway, so it
  // transitions together with the text (as expected).

  // 1) Snapshot the OLD frame (currently shown on cvCurr) into bufOld.
  bufOld.width = W; bufOld.height = H;
  bufOldCtx.clearRect(0, 0, W, H);
  bufOldCtx.drawImage(cvCurr, 0, 0);

  // Clear the back canvas so a stale frame can't bleed through transparent areas.
  if (ctxP && cvPrev) ctxP.clearRect(0, 0, cvPrev.width, cvPrev.height);

  // 2) Render the NEW frame onto cvCurr, then snapshot it into bufNew.
  ctxC.clearRect(0, 0, W, H);
  drawFrame(ctxC);
  bufNew.width = W; bufNew.height = H;
  bufNewCtx.clearRect(0, 0, W, H);
  bufNewCtx.drawImage(cvCurr, 0, 0);

  // 3) Restore cvCurr to the OLD frame. This is essential: main.js delivers
  // every message TWICE (once via IPC 'render', once via executeJavaScript
  // _handleRender), so startTransition runs twice back-to-back. If cvCurr were
  // left showing the NEW frame, the second call would snapshot NEW as bufOld
  // (bufOld === bufNew) → no visible transition. Keeping cvCurr on the OLD
  // frame makes the duplicate call re-capture OLD correctly, and the animation
  // composites bufOld → bufNew from a clean starting point.
  ctxC.clearRect(0, 0, W, H);
  ctxC.drawImage(bufOld, 0, 0);

  transition = { active: true, type, duration, start: performance.now(), progress: 0 };
  // Guard against multiple concurrent rAF chains. main.js delivers each message
  // twice (IPC + executeJavaScript), and rapid slide changes restart the
  // transition; without this guard every call would spawn another animLoop.
  if (!_animRunning) {
    _animRunning = true;
    requestAnimationFrame(animLoop);
  }
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

function animLoop(ts) {
  if (!transition.active) { _animRunning = false; return; }
  const elapsed      = ts - transition.start;
  transition.progress = Math.min(1, elapsed / Math.max(1, transition.duration));
  const p = easeOutCubic(transition.progress);

  applyTransitionFrame(transition.type, p);

  if (transition.progress < 1) {
    requestAnimationFrame(animLoop);
  } else {
    _animRunning = false;
    endTransition();
  }
}

function _bgIsLiveAnimated() {
  return (state.settings.bg_type || '') === 'animated_gradient';
}

function endTransition() {
  transition.active = false;
  // Settle on a clean NEW frame. Re-render via drawFrame so the text canvas is
  // transparent again for image/video/custom backgrounds.
  if (ctxC && cvCurr) {
    ctxC.clearRect(0, 0, cvCurr.width, cvCurr.height);
    drawFrame(ctxC);
  }
}

function applyTransitionFrame(type, p) {
  if (!ctxC || !cvCurr) return;
  const W = cvCurr.width, H = cvCurr.height;
  ctxC.clearRect(0, 0, W, H);

  // Animated-gradient background must keep moving during the transition, so we
  // re-render the live frame each tick (new bg + new text) and just fade the
  // OLD frame out on top instead of compositing two frozen snapshots.
  if (_bgIsLiveAnimated()) {
    drawFrame(ctxC);                       // live animated bg + NEW text
    ctxC.save();
    ctxC.globalAlpha = 1 - p;
    ctxC.drawImage(bufOld, 0, 0);          // OLD frame fading out on top
    ctxC.restore();
    return;
  }

  _renderTransition(type, p, W, H);
}

// ── Transition library (25+ effects) ─────────────────────────────────────────
function _crossfade(p, W, H) {
  ctxC.save(); ctxC.globalAlpha = 1 - p; ctxC.drawImage(bufOld, 0, 0); ctxC.restore();
  ctxC.save(); ctxC.globalAlpha = p;     ctxC.drawImage(bufNew, 0, 0); ctxC.restore();
}
function _clipRectNew(x, y, w, h) {
  ctxC.drawImage(bufOld, 0, 0);
  ctxC.save(); ctxC.beginPath(); ctxC.rect(x, y, w, h); ctxC.clip();
  ctxC.drawImage(bufNew, 0, 0); ctxC.restore();
}

function _renderTransition(type, p, W, H) {
  const o = (f) => Math.round(p * f);
  switch (type) {
    // ── Slides (new covers old) ──────────────────────────────────────────────
    case 'slide_left':  ctxC.drawImage(bufOld, 0, 0); ctxC.drawImage(bufNew, W - o(W), 0); break;
    case 'slide_right': ctxC.drawImage(bufOld, 0, 0); ctxC.drawImage(bufNew, o(W) - W, 0); break;
    case 'slide_up':    ctxC.drawImage(bufOld, 0, 0); ctxC.drawImage(bufNew, 0, H - o(H)); break;
    case 'slide_down':  ctxC.drawImage(bufOld, 0, 0); ctxC.drawImage(bufNew, 0, o(H) - H); break;
    // ── Push (both move) ─────────────────────────────────────────────────────
    case 'push_left':   ctxC.drawImage(bufOld, -o(W), 0); ctxC.drawImage(bufNew, W - o(W), 0); break;
    case 'push_right':  ctxC.drawImage(bufOld, o(W), 0);  ctxC.drawImage(bufNew, o(W) - W, 0); break;
    case 'push_up':     ctxC.drawImage(bufOld, 0, -o(H)); ctxC.drawImage(bufNew, 0, H - o(H)); break;
    case 'push_down':   ctxC.drawImage(bufOld, 0, o(H));  ctxC.drawImage(bufNew, 0, o(H) - H); break;
    // ── Reveal (old slides away, new static) ─────────────────────────────────
    case 'reveal_left':  ctxC.drawImage(bufNew, 0, 0); ctxC.drawImage(bufOld, -o(W), 0); break;
    case 'reveal_right': ctxC.drawImage(bufNew, 0, 0); ctxC.drawImage(bufOld, o(W), 0); break;
    case 'reveal_up':    ctxC.drawImage(bufNew, 0, 0); ctxC.drawImage(bufOld, 0, -o(H)); break;
    case 'reveal_down':  ctxC.drawImage(bufNew, 0, 0); ctxC.drawImage(bufOld, 0, o(H)); break;
    // ── Wipes (hard edge reveal) ─────────────────────────────────────────────
    case 'wipe_left':  _clipRectNew(0, 0, o(W), H); break;
    case 'wipe_right': _clipRectNew(W - o(W), 0, o(W), H); break;
    case 'wipe_up':    _clipRectNew(0, 0, W, o(H)); break;
    case 'wipe_down':  _clipRectNew(0, H - o(H), W, o(H)); break;
    case 'wipe_diag':  _clipRectNew(0, 0, o(W * 1.4), o(H * 1.4)); break;
    // ── Zoom ────────────────────────────────────────────────────────────────
    case 'zoom_in': {
      ctxC.save(); ctxC.globalAlpha = 1 - p; const s1 = 1 + p * 0.15;
      ctxC.translate(W/2, H/2); ctxC.scale(s1, s1); ctxC.translate(-W/2, -H/2);
      ctxC.drawImage(bufOld, 0, 0); ctxC.restore();
      ctxC.save(); ctxC.globalAlpha = p; ctxC.drawImage(bufNew, 0, 0); ctxC.restore(); break;
    }
    case 'zoom_out': {
      ctxC.save(); ctxC.globalAlpha = p; const s2 = 1.18 - p * 0.18;
      ctxC.translate(W/2, H/2); ctxC.scale(s2, s2); ctxC.translate(-W/2, -H/2);
      ctxC.drawImage(bufNew, 0, 0); ctxC.restore();
      ctxC.save(); ctxC.globalAlpha = 1 - p; ctxC.drawImage(bufOld, 0, 0); ctxC.restore(); break;
    }
    // ── Iris (circle) ────────────────────────────────────────────────────────
    case 'iris_open': {
      ctxC.drawImage(bufOld, 0, 0);
      ctxC.save(); ctxC.beginPath();
      ctxC.arc(W/2, H/2, p * Math.hypot(W, H) / 2, 0, 7); ctxC.clip();
      ctxC.drawImage(bufNew, 0, 0); ctxC.restore(); break;
    }
    case 'iris_close': {
      ctxC.drawImage(bufNew, 0, 0);
      ctxC.save(); ctxC.beginPath();
      ctxC.arc(W/2, H/2, (1 - p) * Math.hypot(W, H) / 2, 0, 7); ctxC.clip();
      ctxC.drawImage(bufOld, 0, 0); ctxC.restore(); break;
    }
    // ── Fade through black / white ───────────────────────────────────────────
    case 'fade_black':
    case 'fade_white': {
      const col = type === 'fade_white' ? '#fff' : '#000';
      if (p < 0.5) { ctxC.globalAlpha = 1; ctxC.drawImage(bufOld, 0, 0);
        ctxC.fillStyle = col; ctxC.globalAlpha = p * 2; ctxC.fillRect(0, 0, W, H); }
      else { ctxC.globalAlpha = 1; ctxC.drawImage(bufNew, 0, 0);
        ctxC.fillStyle = col; ctxC.globalAlpha = (1 - p) * 2; ctxC.fillRect(0, 0, W, H); }
      ctxC.globalAlpha = 1; break;
    }
    // ── Flip ─────────────────────────────────────────────────────────────────
    case 'flip_h': {
      if (p < 0.5) { const s = 1 - p * 2; ctxC.save(); ctxC.translate(W/2, 0);
        ctxC.scale(s, 1); ctxC.translate(-W/2, 0); ctxC.drawImage(bufOld, 0, 0); ctxC.restore(); }
      else { const s = (p - 0.5) * 2; ctxC.save(); ctxC.translate(W/2, 0);
        ctxC.scale(s, 1); ctxC.translate(-W/2, 0); ctxC.drawImage(bufNew, 0, 0); ctxC.restore(); }
      break;
    }
    case 'flip_v': {
      if (p < 0.5) { const s = 1 - p * 2; ctxC.save(); ctxC.translate(0, H/2);
        ctxC.scale(1, s); ctxC.translate(0, -H/2); ctxC.drawImage(bufOld, 0, 0); ctxC.restore(); }
      else { const s = (p - 0.5) * 2; ctxC.save(); ctxC.translate(0, H/2);
        ctxC.scale(1, s); ctxC.translate(0, -H/2); ctxC.drawImage(bufNew, 0, 0); ctxC.restore(); }
      break;
    }
    // ── Spin (rotate + zoom crossfade) ───────────────────────────────────────
    case 'spin': {
      ctxC.save(); ctxC.globalAlpha = 1 - p;
      ctxC.translate(W/2, H/2); ctxC.rotate(p * 0.5); ctxC.scale(1 - p*0.3, 1 - p*0.3);
      ctxC.translate(-W/2, -H/2); ctxC.drawImage(bufOld, 0, 0); ctxC.restore();
      ctxC.save(); ctxC.globalAlpha = p;
      ctxC.translate(W/2, H/2); ctxC.rotate((p - 1) * 0.5); ctxC.scale(0.7 + p*0.3, 0.7 + p*0.3);
      ctxC.translate(-W/2, -H/2); ctxC.drawImage(bufNew, 0, 0); ctxC.restore(); break;
    }
    // ── Blinds / bars ────────────────────────────────────────────────────────
    case 'bars_v': {
      ctxC.drawImage(bufOld, 0, 0); const n = 12, bw = W / n;
      ctxC.save(); ctxC.beginPath();
      for (let i = 0; i < n; i++) ctxC.rect(i * bw, 0, bw * p, H);
      ctxC.clip(); ctxC.drawImage(bufNew, 0, 0); ctxC.restore(); break;
    }
    case 'bars_h': {
      ctxC.drawImage(bufOld, 0, 0); const n = 8, bh = H / n;
      ctxC.save(); ctxC.beginPath();
      for (let i = 0; i < n; i++) ctxC.rect(0, i * bh, W, bh * p);
      ctxC.clip(); ctxC.drawImage(bufNew, 0, 0); ctxC.restore(); break;
    }
    case 'checkerboard': {
      ctxC.drawImage(bufOld, 0, 0); const cx = 10, cy = 6, cw = W/cx, ch = H/cy;
      ctxC.save(); ctxC.beginPath();
      for (let i = 0; i < cx; i++) for (let j = 0; j < cy; j++) {
        const phase = ((i + j) % 2) * 0.5;
        const local = Math.max(0, Math.min(1, (p - phase) * 2));
        if (local > 0) ctxC.rect(i*cw, j*ch, cw*local, ch*local);
      }
      ctxC.clip(); ctxC.drawImage(bufNew, 0, 0); ctxC.restore(); break;
    }
    // ── Squeeze ──────────────────────────────────────────────────────────────
    case 'squeeze_h': {
      ctxC.drawImage(bufOld, 0, 0);
      ctxC.save(); ctxC.translate(W/2, 0); ctxC.scale(p, 1); ctxC.translate(-W/2, 0);
      ctxC.drawImage(bufNew, 0, 0); ctxC.restore(); break;
    }
    case 'squeeze_v': {
      ctxC.drawImage(bufOld, 0, 0);
      ctxC.save(); ctxC.translate(0, H/2); ctxC.scale(1, p); ctxC.translate(0, -H/2);
      ctxC.drawImage(bufNew, 0, 0); ctxC.restore(); break;
    }
    // ── Dissolve (random-ish blocks fading in) ───────────────────────────────
    case 'dissolve': {
      ctxC.drawImage(bufOld, 0, 0); const gx = 24, gy = 14, gw = W/gx, gh = H/gy;
      ctxC.save(); ctxC.beginPath();
      for (let i = 0; i < gx; i++) for (let j = 0; j < gy; j++) {
        const r = ((i * 73 + j * 131) % 100) / 100;
        if (r < p) ctxC.rect(i*gw, j*gh, gw + 1, gh + 1);
      }
      ctxC.clip(); ctxC.drawImage(bufNew, 0, 0); ctxC.restore(); break;
    }
    // ── Morph: old scales up + fades, new grows in from slightly small ───────
    case 'morph': {
      ctxC.save();
      ctxC.globalAlpha = 1 - p;
      const so = 1 + p * 0.18;
      ctxC.translate(W / 2, H / 2); ctxC.scale(so, so); ctxC.translate(-W / 2, -H / 2);
      ctxC.drawImage(bufOld, 0, 0);
      ctxC.restore();
      ctxC.save();
      ctxC.globalAlpha = p;
      const sn = 0.88 + p * 0.12;
      ctxC.translate(W / 2, H / 2); ctxC.scale(sn, sn); ctxC.translate(-W / 2, -H / 2);
      ctxC.drawImage(bufNew, 0, 0);
      ctxC.restore();
      break;
    }
    // ── Defaults: fade / crossfade / blur ────────────────────────────────────
    case 'blur':
    case 'fade':
    case 'crossfade':
    default: _crossfade(p, W, H); break;
  }
  ctxC.globalAlpha = 1;
}

// Full list of transitions (shared with the Python settings/theme dropdowns).
const TRANSITION_TYPES = [
  'fade','crossfade','fade_black','fade_white','dissolve',
  'slide_left','slide_right','slide_up','slide_down',
  'push_left','push_right','push_up','push_down',
  'reveal_left','reveal_right','reveal_up','reveal_down',
  'wipe_left','wipe_right','wipe_up','wipe_down','wipe_diag',
  'zoom_in','zoom_out','iris_open','iris_close',
  'flip_h','flip_v','spin','squeeze_h','squeeze_v',
  'bars_v','bars_h','checkerboard','morph','blur','instant',
];
if (typeof window !== 'undefined') window.TRANSITION_TYPES = TRANSITION_TYPES;

// ── Manual (T-bar) transition: operator scrubs the slide change by hand ──────
let _manualActive = false, _manualType = 'fade';
let _manualNextText = '', _manualOldText = '';
function _manualPrep(nextText, type) {
  if (!ctxC || !cvCurr) return;
  const W = cvCurr.width, H = cvCurr.height;
  _manualType    = type || 'fade';
  _manualOldText = state.text;
  _manualNextText = nextText || '';
  // bufOld = current frame
  bufOld.width = W; bufOld.height = H;
  bufOldCtx.clearRect(0, 0, W, H); bufOldCtx.drawImage(cvCurr, 0, 0);
  // render the NEXT text → bufNew
  state.text = _manualNextText; state.lines = _manualNextText.split('\n');
  ctxC.clearRect(0, 0, W, H); drawFrame(ctxC);
  bufNew.width = W; bufNew.height = H;
  bufNewCtx.clearRect(0, 0, W, H); bufNewCtx.drawImage(cvCurr, 0, 0);
  // restore the current frame (keep showing old until the operator scrubs)
  state.text = _manualOldText; state.lines = _manualOldText.split('\n');
  ctxC.clearRect(0, 0, W, H); ctxC.drawImage(bufOld, 0, 0);
  _manualActive = true;
}
function _manualStep(p) {
  if (!_manualActive) return;
  applyTransitionFrame(_manualType, Math.max(0, Math.min(1, p)));
}
function _manualEnd(commit) {
  if (!_manualActive) return;
  _manualActive = false;
  state.text  = commit ? _manualNextText : _manualOldText;
  state.lines = state.text.split('\n');
  renderCurrent();
}

// ── Render current frame (no transition) ─────────────────────────────────────
function renderCurrent() {
  if (!ctxC || !cvCurr) return;
  if (transition.active) return; // animLoop handles it
  // Clear the prev-layer so a stale captured frame never bleeds through the
  // transparent areas of cvCurr (transparent / camera / video backgrounds).
  if (ctxP && cvPrev) ctxP.clearRect(0, 0, cvPrev.width, cvPrev.height);
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

  // ── Presentation slide mode ─────────────────────────────────────────────
  if (state.presMode && state.presSlide) {
    drawPresSlide(ctx, W, H, state.presSlide);
    drawOverlays(ctx, W, H);
    return;
  }

  // Background
  if (state.bgDoc) {
    // Custom animated background renders on canvas-bg behind; keep text
    // canvas transparent so it shows through.
    ctx.clearRect(0, 0, W, H);
  } else if (bgType === 'transparent') {
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
  } else if (bgType === 'camera_gradient') {
    // Camera feed is a DOM element underneath; overlay a tinted gradient
    ctx.clearRect(0, 0, W, H);
    const gc  = s.bg_grad_c1 || '#000033';
    const dir = s.bg_grad_dir || 'Radial';
    const op  = parseFloat(s.bg_grad_opacity || 0.5);
    let grad;
    if (dir === 'Stânga→Dreapta' || dir === 'left') {
      grad = ctx.createLinearGradient(0, 0, W, 0);
    } else if (dir === 'Sus→Jos' || dir === 'top') {
      grad = ctx.createLinearGradient(0, 0, 0, H);
    } else {
      grad = ctx.createRadialGradient(W/2, H/2, 0, W/2, H/2, Math.max(W, H)/2);
    }
    grad.addColorStop(0, _rgbaFromHex(gc, op) || 'rgba(0,0,51,0.5)');
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);
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

  // Text (normal or dual-language) — faded by the manual "Clear Text" dimmer
  const _textOp = 1 - (state.dim.text || 0);
  if (dualState.active) {
    drawDualText();
  } else if (state.text && state.text.trim().length > 0 && _textOp > 0.001) {
    drawText(state.text, _textOp, 0, 0);
  }

  // Bible reference (bottom-right when source is 'bible')
  if (s.source === 'bible' || state.metadata?.source === 'bible') {
    const ref = state.metadata?.reference
              || s.bible_reference
              || '';
    if (ref) drawReference(ref, s, ctx, W, H);
  }

  // Manual "Black" dimmer — fades the whole frame to black (over bg + text)
  if (state.dim.black > 0) {
    ctx.save();
    ctx.globalAlpha = Math.min(1, state.dim.black);
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, W, H);
    ctx.restore();
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

  // Capitalize / all-caps sacred words — only for songs, not Bible verses
  if ((s.sacred_words_enabled === 'true' || s.sacred_words_enabled === true)
      && s.source !== 'bible') {
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

  // ── Chaotic movement (the concert "wow" effect) ─────────────────────────────
  if (s.text_chaos === true || s.text_chaos === 'true') {
    const ct  = performance.now() / 1000;
    const amp = parseFloat(s.text_chaos_amp || 0.04) * Math.min(w, h);
    const csp = parseFloat(s.text_chaos_speed || 1);
    const chx = (Math.sin(ct * csp * 1.7) + Math.sin(ct * csp * 3.3)) * amp * 0.5;
    const chy = (Math.cos(ct * csp * 1.3) + Math.sin(ct * csp * 2.1)) * amp * 0.5;
    ctxC.translate(chx, chy);
    ctxC.rotate(Math.sin(ct * csp * 0.9) * 0.05);
  }

  const maxW = w - margin * 2;

  // Bible: reserve a band so the VERSE never overlaps the reference. Applies to
  // the preset positions only — a custom bible_ref_zone means the operator has
  // placed things manually and takes responsibility.
  let _reserveTop = 0, _reserveBottom = 0;
  const _isBible = (s.source === 'bible' ||
                    (state.metadata && state.metadata.source === 'bible'));
  const _hasRef = _isBible && ((state.metadata && state.metadata.reference) || s.bible_reference);
  if (_hasRef && !(s.bible_ref_zone && typeof s.bible_ref_zone === 'object')) {
    const _band = parseInt(s.ref_font_size || 24) +
                  parseInt(s.ref_padding != null ? s.ref_padding : 8) * 2 +
                  Math.round(Math.min(w, h) * 0.035);
    if ((s.ref_position || 'bottom_right').indexOf('top') === 0) _reserveTop = _band;
    else _reserveBottom = _band;
  }
  const maxH = h - margin * 2 - _reserveTop - _reserveBottom;

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
    startY = margin + _reserveTop + currentSize * 0.85;
  } else if (valign === 'bottom') {
    startY = h - margin - _reserveBottom - totalH + currentSize * 0.85;
  } else {
    startY = margin + _reserveTop + (maxH - totalH) / 2 + currentSize * 0.85;
  }

  // ── Horizontal alignment ───────────────────────────────────────────────────
  const align = s.text_align || 'center';
  ctxC.textAlign    = align === 'left' ? 'left' : align === 'right' ? 'right' : 'center';
  ctxC.textBaseline = 'alphabetic';
  const baseX = align === 'left' ? margin
              : align === 'right' ? w - margin
              : w / 2;

  // ── Echo: big faint copy of the text behind (concert "ghost lyric" look) ────
  if (s.text_echo === true || s.text_echo === 'true') {
    const escale = parseFloat(s.text_echo_scale || 2.2);
    const eop    = parseFloat(s.text_echo_opacity || 0.12);
    ctxC.save();
    ctxC.globalAlpha = eop;
    ctxC.fillStyle   = s.text_echo_color || color;
    ctxC.textAlign   = 'center';
    ctxC.textBaseline = 'middle';
    const efs = Math.round(currentSize * escale);
    ctxC.font = `${italic ? 'italic ' : ''}${bold ? 'bold ' : ''}${efs}px "${family}"`;
    const elh = efs * 1.05;
    const ey0 = h / 2 - ((lines.length - 1) * elh) / 2;
    lines.forEach((line, i) => { if (line) ctxC.fillText(line, w / 2, ey0 + i * elh); });
    ctxC.restore();
    ctxC.textBaseline = 'alphabetic';
  }

  // ── Cascade mode (current text repeated, centre highlighted) ────────────────
  if (s.text_cascade === true || s.text_cascade === 'true') {
    _drawCascadeText(s, lines, currentSize, lineH, w, h, color, family, bold, italic);
    ctxC.restore();
    return;
  }

  // ── Text box background (FreeShow-style) ────────────────────────────────────
  if (s.text_box_enabled === true || s.text_box_enabled === 'true') {
    drawTextBox(lines, lineH, startY, ctxC, w, h, s, currentSize, align, baseX);
  }

  // ── Text fill: solid / gradient / animated gradient ─────────────────────────
  const _textFill = (yTop, yBot) => {
    const ct = s.text_color_type || 'solid';
    if (ct !== 'gradient' && ct !== 'animated') return color;
    let from = s.text_grad_from || color || '#ffffff';
    let to   = s.text_grad_to   || '#9ec5ff';
    if (ct === 'animated') {
      const k = (Math.sin(performance.now() / 1000 * 0.6) + 1) / 2;
      const a = _mixHexJS(from, to, k), b = _mixHexJS(to, from, k);
      from = a; to = b;
    }
    const g = ctxC.createLinearGradient(0, yTop, 0, yBot);
    g.addColorStop(0, from); g.addColorStop(1, to);
    return g;
  };

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

    // Neon glow (strong coloured halo around the text)
    if (s.text_glow === true || s.text_glow === 'true') {
      ctxC.shadowColor   = s.text_glow_color || color;
      ctxC.shadowBlur    = parseInt(s.text_glow_size || 26);
      ctxC.shadowOffsetX = 0;
      ctxC.shadowOffsetY = 0;
    } else if (shadow) {
      ctxC.shadowColor   = _rgbaFromHex(s.shadow_color, 0.85) || 'rgba(0,0,0,0.85)';
      ctxC.shadowBlur    = 8;
      ctxC.shadowOffsetX = 3;
      ctxC.shadowOffsetY = 3;
    } else {
      ctxC.shadowColor   = 'transparent';
      ctxC.shadowBlur    = 0;
      ctxC.shadowOffsetX = 0;
      ctxC.shadowOffsetY = 0;
    }

    ctxC.fillStyle = _textFill(y - currentSize * 0.85, y + currentSize * 0.2);
    ctxC.fillText(line, baseX, y);
  });

  ctxC.restore();
}

// Hex blend helper for animated text colour.
function _mixHexJS(a, b, t) {
  const pa = parseInt(String(a).replace('#', ''), 16);
  const pb = parseInt(String(b).replace('#', ''), 16);
  const r = Math.round(((pa >> 16) & 255) + (((pb >> 16) & 255) - ((pa >> 16) & 255)) * t);
  const g = Math.round(((pa >> 8) & 255) + (((pb >> 8) & 255) - ((pa >> 8) & 255)) * t);
  const bl = Math.round((pa & 255) + ((pb & 255) - (pa & 255)) * t);
  return `rgb(${r},${g},${bl})`;
}

// ── Cascade text: slide text repeated vertically, centre line highlighted ────
function _drawCascadeText(s, lines, size, lineH, w, h, baseColor, family, bold, italic) {
  const copies   = Math.max(3, parseInt(s.cascade_lines || 5));
  const gap      = parseFloat(s.cascade_gap || 1.15);
  const hlColor  = s.cascade_hl_color  || baseColor;
  const dimColor = s.cascade_dim_color || baseColor;
  const dimOp    = parseFloat(s.cascade_dim_opacity || 0.30);
  const glow     = s.cascade_glow === true || s.cascade_glow === 'true';
  const half     = Math.floor(copies / 2);
  const blockH   = Math.max(1, lines.length) * lineH;
  const copyGap  = blockH * gap;

  ctxC.textAlign = 'center';
  ctxC.textBaseline = 'alphabetic';
  for (let c = -half; c <= half; c++) {
    const dist = Math.abs(c);
    const isCenter = c === 0;
    const op = isCenter ? 1 : dimOp * (1 - dist / (half + 1));
    if (op <= 0.01) continue;
    const sc = isCenter ? 1.0 : (1 - dist * 0.05);
    ctxC.save();
    ctxC.globalAlpha = op;
    ctxC.shadowColor = 'transparent'; ctxC.shadowBlur = 0;
    ctxC.fillStyle = isCenter ? hlColor : dimColor;
    const fs = Math.max(8, Math.round(size * sc));
    ctxC.font = `${italic ? 'italic ' : ''}${bold ? 'bold ' : ''}${fs}px "${family}"`;
    if (isCenter && glow) { ctxC.shadowColor = hlColor; ctxC.shadowBlur = size * 0.45; }
    const clh = lineH * sc;
    const cy  = h / 2 + c * copyGap;
    const y0  = cy - ((lines.length - 1) * clh) / 2 + fs * 0.34;
    lines.forEach((line, i) => { if (line) ctxC.fillText(line, w / 2, y0 + i * clh); });
    ctxC.restore();
  }
}

// ── Hex (#RGB/#RRGGBB/#AARRGGBB) → rgba() string ──────────────────────────────
function _rgbaFromHex(hex, fallbackAlpha) {
  if (!hex || typeof hex !== 'string') return null;
  let h = hex.replace('#', '');
  let a = (fallbackAlpha != null) ? fallbackAlpha : 1;
  let r, g, b;
  if (h.length === 8) {                       // AARRGGBB
    a = parseInt(h.slice(0, 2), 16) / 255;
    r = parseInt(h.slice(2, 4), 16);
    g = parseInt(h.slice(4, 6), 16);
    b = parseInt(h.slice(6, 8), 16);
  } else if (h.length === 6) {
    r = parseInt(h.slice(0, 2), 16);
    g = parseInt(h.slice(2, 4), 16);
    b = parseInt(h.slice(4, 6), 16);
  } else if (h.length === 3) {
    r = parseInt(h[0] + h[0], 16);
    g = parseInt(h[1] + h[1], 16);
    b = parseInt(h[2] + h[2], 16);
  } else {
    return null;
  }
  if ([r, g, b].some(isNaN)) return null;
  return `rgba(${r},${g},${b},${a})`;
}

// ── Bible reference ───────────────────────────────────────────────────────────
function drawReference(ref, s, ctx, W, H) {
  if (!ref || !ref.trim()) return;

  const family   = s.font_family   || 'Arial';
  const refSize  = parseInt(s.ref_font_size || 24);
  const refColor = s.ref_color     || '#aaaaaa';
  const refBold  = s.ref_bold === true || s.ref_bold === 'true';
  const refItalic = (s.ref_italic === undefined || s.ref_italic === null)
                 ? true                                   // legacy default: italic
                 : (s.ref_italic === true || s.ref_italic === 'true');
  const refUpper = s.ref_uppercase === true || s.ref_uppercase === 'true';
  const bgEnabled = s.ref_bg_enabled === true || s.ref_bg_enabled === 'true';
  const bgColor   = _rgbaFromHex(s.ref_bg_color, 0.6) || 'rgba(0,0,0,0.6)';
  const bgPad     = parseInt(s.ref_padding ?? 8);
  const rawMargin = parseFloat(s.margin || 0.06);
  const margin   = rawMargin < 2
    ? Math.round(Math.min(W, H) * rawMargin)
    : parseInt(rawMargin);

  const refText = refUpper ? ref.toUpperCase() : ref;
  const fontStr = `${refItalic ? 'italic ' : ''}${refBold ? 'bold ' : ''}${refSize}px "${family}"`;

  ctx.save();
  ctx.font = fontStr;
  const tw = ctx.measureText(refText).width;

  const refZone = s.bible_ref_zone;
  let tx, ty, baseline, halign;
  if (refZone && typeof refZone === 'object') {
    const rx = refZone.x / 100 * W;
    const ry = refZone.y / 100 * H;
    const rw = refZone.w / 100 * W;
    const rh = refZone.h / 100 * H;
    tx = rx + rw; ty = ry + rh / 2; baseline = 'middle'; halign = 'right';
  } else {
    const refPos = s.ref_position || 'bottom_right';
    if      (refPos === 'bottom_left')   { tx = margin;     ty = H - margin; baseline = 'bottom'; halign = 'left';   }
    else if (refPos === 'bottom_center') { tx = W / 2;      ty = H - margin; baseline = 'bottom'; halign = 'center'; }
    else if (refPos === 'top_right')     { tx = W - margin; ty = margin + refSize; baseline = 'top'; halign = 'right'; }
    else if (refPos === 'top_left')      { tx = margin;     ty = margin + refSize; baseline = 'top'; halign = 'left';   }
    else if (refPos === 'top_center')    { tx = W / 2;      ty = margin + refSize; baseline = 'top'; halign = 'center'; }
    else                                 { tx = W - margin; ty = H - margin; baseline = 'bottom'; halign = 'right';  }
  }

  // Background box behind reference
  if (bgEnabled) {
    const boxX = halign === 'left'  ? tx - bgPad
               : halign === 'right' ? tx - tw - bgPad
               : tx - tw / 2 - bgPad;
    let boxY;
    if (baseline === 'middle')      boxY = ty - refSize / 2 - bgPad;
    else if (baseline === 'top')    boxY = ty - bgPad;
    else                            boxY = ty - refSize - bgPad;
    ctx.fillStyle = bgColor;
    roundRect(ctx, boxX, boxY, tw + bgPad * 2, refSize + bgPad * 2, 6);
    ctx.fill();
  }

  ctx.shadowColor   = 'rgba(0,0,0,0.8)';
  ctx.shadowBlur    = 6;
  ctx.shadowOffsetX = 2;
  ctx.shadowOffsetY = 2;
  ctx.textAlign     = halign;
  ctx.textBaseline  = baseline;
  ctx.fillStyle     = refColor;
  ctx.fillText(refText, tx, ty);

  ctx.restore();
}

// ── Metadata watermark (title/author/category watermark on live screen) ───────
function drawMetadata(ctx, W, H) {
  const crRaw = state.settings.copyright;
  if (!crRaw) return;
  let cr;
  try { cr = typeof crRaw === 'string' ? JSON.parse(crRaw) : crRaw; } catch { return; }
  if (!cr || !cr.enabled) return;

  const meta = state.metadata || {};
  let text = '';
  switch (cr.mode) {
    case 'title':          text = meta.title  || ''; break;
    case 'author':         text = meta.author || ''; break;
    case 'category':       text = meta.category || ''; break;
    case 'source':         text = meta.source  || ''; break;
    case 'custom':         text = cr.custom    || ''; break;
    default:               text = [meta.title, meta.author].filter(Boolean).join(' — ');
  }
  if (!text.trim()) return;

  const fontSize = parseInt(cr.font_size || 14);
  const opacity  = parseFloat(cr.opacity  || 0.4);
  const color    = cr.color    || '#ffffff';
  const position = cr.position || 'bottom_right';
  const pad      = 20;

  ctx.save();
  ctx.globalAlpha   = opacity;
  ctx.font          = `italic ${fontSize}px "Segoe UI", Arial, sans-serif`;
  ctx.shadowColor   = 'rgba(0,0,0,0.9)';
  ctx.shadowBlur    = 8;
  ctx.shadowOffsetX = 1;
  ctx.shadowOffsetY = 1;
  ctx.fillStyle     = color;

  const textW = ctx.measureText(text).width;
  let x, y;
  ctx.textBaseline = 'bottom';
  if      (position === 'bottom_right')  { x = W - textW - pad; y = H - pad; }
  else if (position === 'bottom_left')   { x = pad;             y = H - pad; }
  else if (position === 'bottom_center') { x = (W - textW) / 2; y = H - pad; }
  else if (position === 'top_right')     { x = W - textW - pad; y = fontSize + pad; }
  else if (position === 'top_left')      { x = pad;             y = fontSize + pad; }
  else                                   { x = W - textW - pad; y = H - pad; }

  ctx.fillText(text, x, y);
  ctx.restore();
}

// ══════════════════════════════════════════════════════════════════════════════
// Presentation slide renderer
// ══════════════════════════════════════════════════════════════════════════════

const PRES_W = 1920;
const PRES_H = 1080;

// Per-element animation state: elementId → {opacity, tx, ty, scale}
const _presAnimState = new Map();

function _startPresAnimations(elements, transitionDur) {
  _presAnimState.clear();
  elements.forEach((el, idx) => {
    const anim = el.animation || {};
    const entrance = anim.entrance || 'none';
    if (entrance === 'none') return;
    const delay    = parseInt(anim.delay    || 0,   10);
    const duration = parseInt(anim.duration || 500, 10);
    const id = el._id || idx;
    _presAnimState.set(id, {
      entrance, delay, duration,
      startTime: performance.now() + transitionDur + delay,
      done: false,
    });
  });
}

function _getPresElemOpacity(el, idx) {
  const id = el._id || idx;
  const st = _presAnimState.get(id);
  if (!st || st.done) return { opacity: 1, tx: 0, ty: 0, scale: 1 };
  const now     = performance.now();
  const elapsed = now - st.startTime;
  if (elapsed < 0) return { opacity: 0, tx: _entranceTx(st.entrance, el),
                             ty: _entranceTy(st.entrance, el), scale: _entranceScale(st.entrance) };
  const t = Math.min(1, elapsed / st.duration);
  const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
  if (t >= 1) st.done = true;
  return {
    opacity: eased,
    tx: _entranceTx(st.entrance, el) * (1 - eased),
    ty: _entranceTy(st.entrance, el) * (1 - eased),
    scale: st.entrance === 'zoom_in' ? (0.2 + 0.8 * eased) :
           st.entrance === 'bounce'  ? _bounceScale(t) : 1,
  };
}

function _entranceTx(e, el) {
  const w = el.w || 400;
  if (e === 'slide_left')  return  w + 200;
  if (e === 'slide_right') return -(w + 200);
  return 0;
}
function _entranceTy(e, el) {
  const h = el.h || 100;
  if (e === 'slide_up')   return  h + 100;
  if (e === 'slide_down') return -(h + 100);
  return 0;
}
function _entranceScale(e) {
  return (e === 'zoom_in' || e === 'bounce') ? 0.2 : 1;
}
function _bounceScale(t) {
  if (t < 0.6) return 0.2 + (t / 0.6) * 1.1;
  if (t < 0.8) return 1.3 - ((t - 0.6) / 0.2) * 0.3;
  return 1.0 + ((1 - t) / 0.2) * 0.05;
}

function _presGradient(ctx, x, y, w, h, from, to, angle) {
  const rad = (angle || 90) * Math.PI / 180;
  const cx = x + w/2, cy = y + h/2;
  const dx = Math.cos(rad) * w/2, dy = Math.sin(rad) * h/2;
  const g = ctx.createLinearGradient(cx-dx, cy-dy, cx+dx, cy+dy);
  g.addColorStop(0, from || '#5294e2');
  g.addColorStop(1, to   || '#1a1a5a');
  return g;
}

function drawPresSlide(ctx, W, H, slide) {
  const sx = W / PRES_W;
  const sy = H / PRES_H;

  // ── Background ──────────────────────────────────────────────────────────
  const bgType = slide.bg_type || 'solid';
  if (bgType === 'gradient') {
    const angle = slide.bg_gradient_angle || 135;
    const rad   = angle * Math.PI / 180;
    const cx = W/2, cy = H/2;
    const dx = Math.cos(rad) * W/2, dy = Math.sin(rad) * H/2;
    const g = ctx.createLinearGradient(cx-dx, cy-dy, cx+dx, cy+dy);
    g.addColorStop(0, slide.bg_gradient_from || '#1a1a2a');
    g.addColorStop(1, slide.bg_gradient_to   || '#000000');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
  } else if (bgType === 'image' && slide.bg_image) {
    ctx.fillStyle = slide.bg_color || '#000000';
    ctx.fillRect(0, 0, W, H);
    _drawPresImage(ctx, slide.bg_image, 0, 0, W, H, 1.0, 'cover');
  } else {
    ctx.fillStyle = slide.bg_color || '#000000';
    ctx.fillRect(0, 0, W, H);
  }

  // ── Elements sorted by z-index ──────────────────────────────────────────
  const elements = (slide.elements || [])
    .filter(e => e.visible !== false)
    .sort((a, b) => (a.z || 0) - (b.z || 0));

  elements.forEach((el, idx) => {
    const ex  = (el.x || 0) * sx;
    const ey  = (el.y || 0) * sy;
    const ew  = (el.w || 100) * sx;
    const eh  = (el.h || 40)  * sy;
    const rot = el.rotation || 0;
    const baseOpacity = parseFloat(el.opacity !== undefined ? el.opacity : 1.0);

    const { opacity: animOp, tx, ty, scale } = _getPresElemOpacity(el, idx);
    const finalOpacity = baseOpacity * animOp;

    ctx.save();
    ctx.globalAlpha = finalOpacity;

    // Apply transform (rotation + animation offset + scale)
    const cx = ex + ew/2 + tx * sx;
    const cy = ey + eh/2 + ty * sy;
    ctx.translate(cx, cy);
    if (rot)   ctx.rotate(rot * Math.PI / 180);
    if (scale !== 1) ctx.scale(scale, scale);
    ctx.translate(-ew/2, -eh/2);

    _drawPresElement(ctx, el, ew, eh, sx, sy);
    ctx.restore();
  });
}

function _drawPresElement(ctx, el, ew, eh, sx, sy) {
  const kind = el.type || '';

  if (kind === 'text') {
    _drawPresText(ctx, el, ew, eh, sx);
  } else if (kind === 'image') {
    _drawPresImage(ctx, el.path, 0, 0, ew, eh,
                   parseFloat(el.opacity || 1));
  } else if (['rect','ellipse','triangle','star','arrow','line'].includes(kind)) {
    _drawPresShape(ctx, el, ew, eh, sx);
  } else if (kind === 'code') {
    _drawPresCode(ctx, el, ew, eh, sx);
  } else if (kind === 'table') {
    _drawPresTable(ctx, el, ew, eh, sx);
  } else if (kind === 'chart') {
    _drawPresChart(ctx, el, ew, eh, sx);
  } else if (kind === 'diagram') {
    _drawPresDiagram(ctx, el, ew, eh, sx);
  }
}

function _drawPresText(ctx, el, ew, eh, sx) {
  const bg = el.bg_color;
  if (bg) {
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, ew, eh);
  }
  const fontSize   = Math.max(6, Math.round((el.font_size || 48) * sx));
  const fontFamily = el.font || 'Segoe UI';
  const bold       = el.bold   ? 'bold '   : '';
  const italic_    = el.italic ? 'italic ' : '';
  ctx.font         = `${bold}${italic_}${fontSize}px "${fontFamily}", Arial`;
  ctx.fillStyle    = el.color || '#ffffff';
  ctx.textBaseline = 'top';

  const align = el.align || 'center';
  ctx.textAlign = align;

  const x = align === 'center' ? ew/2 : align === 'right' ? ew - 4 : 4;
  const lineSpacing = parseFloat(el.line_spacing || 1.2);
  const lineH = fontSize * lineSpacing;
  const text  = el.text || '';
  const lines = _wrapPresText(ctx, text, ew - 8);
  const totalH = lines.length * lineH;
  let y = Math.max(4, (eh - totalH) / 2);
  for (const line of lines) {
    if (y + lineH > eh) break;
    ctx.fillText(line, x, y);
    y += lineH;
  }
  if (el.underline) {
    ctx.strokeStyle = el.color || '#ffffff';
    ctx.lineWidth   = Math.max(1, fontSize * 0.05);
    lines.forEach((line, i) => {
      const ty = Math.max(4, (eh - totalH) / 2) + i * lineH + fontSize;
      const tw = ctx.measureText(line).width;
      const lx = align === 'center' ? (ew - tw)/2 :
                 align === 'right'  ? ew - 4 - tw : 4;
      ctx.beginPath();
      ctx.moveTo(lx, ty);
      ctx.lineTo(lx + tw, ty);
      ctx.stroke();
    });
  }
}

function _wrapPresText(ctx, text, maxW) {
  const lines = [];
  for (const para of text.split('\n')) {
    if (ctx.measureText(para).width <= maxW) {
      lines.push(para);
    } else {
      const words = para.split(' ');
      let cur = '';
      for (const w of words) {
        const test = cur ? cur + ' ' + w : w;
        if (ctx.measureText(test).width > maxW && cur) {
          lines.push(cur);
          cur = w;
        } else {
          cur = test;
        }
      }
      if (cur) lines.push(cur);
    }
  }
  return lines;
}

const _presImgCache = new Map();
function _drawPresImage(ctx, path, x, y, w, h, opacity, fit) {
  if (!path) return;
  const cached = _presImgCache.get(path);
  if (cached) {
    _blitPresImg(ctx, cached, x, y, w, h, fit);
    return;
  }
  const img = new Image();
  img.onload = () => {
    _presImgCache.set(path, img);
    // re-render will pick it up on next frame
  };
  const fixedPath = path.replace(/\\/g, '/').replace(/^([A-Za-z]):/, '/$1:');
  img.src = 'file:///' + fixedPath;
}

function _blitPresImg(ctx, img, x, y, w, h, fit) {
  if (fit === 'cover') {
    const scale = Math.max(w / img.width, h / img.height);
    const sw = img.width * scale, sh = img.height * scale;
    ctx.drawImage(img, x + (w-sw)/2, y + (h-sh)/2, sw, sh);
  } else {
    const scale = Math.min(w / img.width, h / img.height);
    const sw = img.width * scale, sh = img.height * scale;
    ctx.drawImage(img, x + (w-sw)/2, y + (h-sh)/2, sw, sh);
  }
}

function _drawPresShape(ctx, el, ew, eh, sx) {
  const kind = el.type;
  ctx.globalAlpha *= parseFloat(el.opacity !== undefined ? el.opacity : 1);
  const bw = Math.max(0, (el.border_width || 0) * sx);

  // Fill
  if (el.fill_type === 'gradient') {
    ctx.fillStyle = _presGradient(ctx, 0, 0, ew, eh,
      el.gradient_from, el.gradient_to, el.gradient_angle);
  } else {
    ctx.fillStyle = el.fill || el.color || '#5294e2';
  }
  ctx.strokeStyle = el.border_color || 'transparent';
  ctx.lineWidth   = bw;

  if (kind === 'rect') {
    const r = (el.border_radius || 0) * sx;
    if (r > 0) {
      ctx.beginPath();
      ctx.roundRect(0, 0, ew, eh, r);
      ctx.fill();
      if (bw) ctx.stroke();
    } else {
      ctx.fillRect(0, 0, ew, eh);
      if (bw) ctx.strokeRect(0, 0, ew, eh);
    }
  } else if (kind === 'ellipse') {
    ctx.beginPath();
    ctx.ellipse(ew/2, eh/2, ew/2, eh/2, 0, 0, Math.PI*2);
    ctx.fill();
    if (bw) ctx.stroke();
  } else if (kind === 'triangle') {
    ctx.beginPath();
    ctx.moveTo(ew/2, 0);
    ctx.lineTo(ew, eh);
    ctx.lineTo(0, eh);
    ctx.closePath();
    ctx.fill();
    if (bw) ctx.stroke();
  } else if (kind === 'star') {
    const pts = el.points || 5;
    const outer = Math.min(ew, eh) / 2;
    const inner = outer / 2.5;
    ctx.beginPath();
    for (let i = 0; i < pts * 2; i++) {
      const r = i % 2 === 0 ? outer : inner;
      const a = Math.PI / pts * i - Math.PI / 2;
      i === 0
        ? ctx.moveTo(ew/2 + r*Math.cos(a), eh/2 + r*Math.sin(a))
        : ctx.lineTo(ew/2 + r*Math.cos(a), eh/2 + r*Math.sin(a));
    }
    ctx.closePath();
    ctx.fill();
    if (bw) ctx.stroke();
  } else if (kind === 'arrow') {
    const hw = eh * 0.35, nw = ew * 0.60;
    ctx.beginPath();
    ctx.moveTo(0, (eh-hw)/2);
    ctx.lineTo(nw, (eh-hw)/2);
    ctx.lineTo(nw, 0);
    ctx.lineTo(ew, eh/2);
    ctx.lineTo(nw, eh);
    ctx.lineTo(nw, (eh+hw)/2);
    ctx.lineTo(0, (eh+hw)/2);
    ctx.closePath();
    ctx.fill();
    if (bw) ctx.stroke();
  } else if (kind === 'line') {
    ctx.beginPath();
    ctx.strokeStyle = el.color || '#ffffff';
    ctx.lineWidth   = Math.max(1, (el.line_width || 3) * sx);
    ctx.moveTo(0, 0);
    ctx.lineTo(ew, eh);
    ctx.stroke();
  }
}

function _drawPresCode(ctx, el, ew, eh, sx) {
  ctx.fillStyle = el.bg_color || '#1e1e2e';
  ctx.fillRect(0, 0, ew, eh);
  ctx.strokeStyle = '#333344';
  ctx.lineWidth = 1;
  ctx.strokeRect(0, 0, ew, eh);
  const fs = Math.max(6, Math.round((el.font_size || 18) * sx));
  ctx.font = `${fs}px Consolas, monospace`;
  ctx.fillStyle = el.text_color || '#cdd6f4';
  ctx.textBaseline = 'top';
  ctx.textAlign    = 'left';
  const code  = el.code_text || '';
  const lineH = fs * 1.35;
  let y = 8;
  for (const line of code.split('\n')) {
    if (y > eh - lineH) break;
    ctx.fillText(line, 8, y);
    y += lineH;
  }
}

function _drawPresTable(ctx, el, ew, eh, sx) {
  const rows  = el.rows  || 3;
  const cols  = el.cols  || 3;
  const cells = el.cells || [];
  const cw = ew / cols;
  const ch = eh / rows;
  const fs = Math.max(6, Math.round((el.font_size || 18) * sx));
  ctx.font         = `${fs}px "Segoe UI", Arial`;
  ctx.textBaseline = 'middle';
  ctx.textAlign    = 'center';
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const x = c * cw, y = r * ch;
      ctx.fillStyle = r === 0
        ? (el.header_bg    || '#1a3a5a')
        : (el.cell_bg      || '#1c1c1c');
      ctx.fillRect(x, y, cw, ch);
      ctx.strokeStyle = el.border_color || '#333333';
      ctx.lineWidth   = 1;
      ctx.strokeRect(x, y, cw, ch);
      const text = (cells[r] && cells[r][c]) ? String(cells[r][c]) : '';
      ctx.fillStyle = r === 0
        ? (el.header_color || '#ffffff')
        : (el.cell_color   || '#e0e0e0');
      ctx.fillText(text, x + cw/2, y + ch/2);
    }
  }
}

// ── Chart renderer (Canvas 2D) ────────────────────────────────────────────────
function _drawPresChart(ctx, el, ew, eh, sx) {
  const chartType  = el.chart_type || 'bar';
  const bg         = el.bg_color   || '#1c1c1c';
  const textCol    = el.text_color || '#e0e0e0';
  const valCol     = el.value_color|| '#5294e2';
  const gridCol    = el.grid_color || '#2a2a2a';
  const title      = el.title      || '';
  const labels     = el.labels     || [];
  const values     = (el.values    || []).map(Number).filter(v => !isNaN(v));
  const showVals   = el.show_values !== false;

  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, ew, eh);

  let titleH = 0;
  if (title) {
    const fsTit = Math.max(8, Math.round(eh * 0.055));
    ctx.font = `bold ${fsTit}px "Segoe UI", Arial`;
    ctx.fillStyle = textCol;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    titleH = eh * 0.12;
    ctx.fillText(title, ew / 2, titleH / 2);
  }
  if (!values.length) return;

  const n = values.length;
  const lbls = labels.slice(0, n).concat(Array(Math.max(0, n - labels.length)).fill(''));

  if (chartType === 'pie') {
    _drawPresChartPie(ctx, ew, eh, titleH, lbls, values, valCol, textCol, showVals);
  } else if (chartType === 'line') {
    _drawPresChartLine(ctx, ew, eh, titleH, lbls, values, valCol, textCol, gridCol, showVals);
  } else {
    _drawPresChartBar(ctx, ew, eh, titleH, lbls, values, valCol, textCol, gridCol, showVals);
  }
}

function _drawPresChartBar(ctx, ew, eh, titleH, labels, values, valCol, textCol, gridCol, showVals) {
  const n = values.length;
  const maxVal = Math.max(...values, 1);
  const padL = ew*0.09, padR = ew*0.03, padT = titleH + eh*0.05, padB = eh*0.18;
  const cw = ew - padL - padR, ch = eh - padT - padB;
  const fsSm = Math.max(5, Math.round(eh * 0.038));
  ctx.font = `${fsSm}px "Segoe UI", Arial`;

  // Grid
  for (let i = 0; i <= 4; i++) {
    const gy = padT + ch * (1 - i / 4);
    ctx.strokeStyle = gridCol; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(padL, gy); ctx.lineTo(padL + cw, gy); ctx.stroke();
    ctx.fillStyle = textCol; ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    ctx.fillText(Math.round(maxVal * i / 4), padL - 3, gy);
  }
  // Axes
  ctx.strokeStyle = '#555'; ctx.lineWidth = Math.max(1, eh * 0.005);
  ctx.beginPath(); ctx.moveTo(padL, padT); ctx.lineTo(padL, padT+ch);
  ctx.lineTo(padL+cw, padT+ch); ctx.stroke();

  const slot = cw / n, bw = slot * 0.6;
  for (let i = 0; i < n; i++) {
    const bh = (values[i] / maxVal) * ch;
    const bx = padL + slot*i + slot*0.2, by = padT + ch - bh;
    if (bh > 0) {
      const grad = ctx.createLinearGradient(bx, by, bx, by + bh);
      grad.addColorStop(0, _lightenHex(valCol, 30));
      grad.addColorStop(1, valCol);
      ctx.fillStyle = grad;
      ctx.fillRect(bx, by, bw, bh);
    }
    ctx.fillStyle = textCol; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    ctx.fillText(String(labels[i] || ''), bx + bw/2, padT+ch+3);
    if (showVals && bh > 0) {
      ctx.textBaseline = 'bottom';
      ctx.fillText(values[i] % 1 === 0 ? String(values[i]) : values[i].toFixed(1),
                   bx + bw/2, Math.max(by, 2));
    }
  }
}

function _drawPresChartLine(ctx, ew, eh, titleH, labels, values, valCol, textCol, gridCol, showVals) {
  const n = values.length;
  const maxVal = Math.max(...values, 1);
  const padL = ew*0.09, padR = ew*0.03, padT = titleH + eh*0.05, padB = eh*0.18;
  const cw = ew - padL - padR, ch = eh - padT - padB;
  const fsSm = Math.max(5, Math.round(eh * 0.038));
  const spacing = n > 1 ? cw / (n - 1) : cw;

  for (let i = 0; i <= 4; i++) {
    const gy = padT + ch * (1 - i / 4);
    ctx.strokeStyle = gridCol; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(padL, gy); ctx.lineTo(padL+cw, gy); ctx.stroke();
    ctx.font = `${fsSm}px "Segoe UI", Arial`; ctx.fillStyle = textCol;
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    ctx.fillText(Math.round(maxVal * i / 4), padL - 3, gy);
  }
  ctx.strokeStyle = '#555'; ctx.lineWidth = Math.max(1, eh*0.005);
  ctx.beginPath(); ctx.moveTo(padL, padT); ctx.lineTo(padL, padT+ch);
  ctx.lineTo(padL+cw, padT+ch); ctx.stroke();

  const pts = values.map((v, i) => ({
    x: padL + spacing * i,
    y: padT + ch * (1 - v / maxVal)
  }));

  ctx.strokeStyle = valCol; ctx.lineWidth = Math.max(2, eh * 0.012);
  ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
  ctx.stroke();

  const r2 = Math.max(3, eh * 0.018);
  ctx.fillStyle = valCol; ctx.strokeStyle = '#fff'; ctx.lineWidth = Math.max(1, r2*0.4);
  pts.forEach(pt => { ctx.beginPath(); ctx.arc(pt.x, pt.y, r2, 0, Math.PI*2); ctx.fill(); ctx.stroke(); });

  const slot = cw / n;
  ctx.font = `${fsSm}px "Segoe UI", Arial`; ctx.fillStyle = textCol;
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  labels.forEach((lbl, i) => {
    const px = n > 1 ? padL + spacing * i : padL + cw/2;
    ctx.fillText(String(lbl || ''), px, padT + ch + 3);
  });
}

function _drawPresChartPie(ctx, ew, eh, titleH, labels, values, valCol, textCol, showVals) {
  const total = values.reduce((a, b) => a + b, 0) || 1;
  const pieH  = eh - titleH;
  const size  = Math.min(ew * 0.55, pieH * 0.85);
  const cx = ew * 0.33, cy = titleH + pieH / 2, r = size / 2;
  const colors = values.map((_, i) => _hsvToHex((_hexToHue(valCol) + i*0.15) % 1, 0.7, 0.75 + 0.1*(i%2)));

  let start = -Math.PI / 2;
  values.forEach((val, i) => {
    const span = (val / total) * Math.PI * 2;
    ctx.fillStyle = colors[i];
    ctx.strokeStyle = '#1c1c1c'; ctx.lineWidth = Math.max(1, r*0.02);
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, r, start, start+span); ctx.closePath();
    ctx.fill(); ctx.stroke();
    start += span;
  });

  const fsSm = Math.max(5, Math.round(eh * 0.042));
  ctx.font = `${fsSm}px "Segoe UI", Arial`;
  const lx = cx + r + 14;
  const entH = Math.min(eh * 0.085, (eh - titleH - 8) / Math.max(labels.length, 1));
  labels.forEach((lbl, i) => {
    const ly = titleH + 8 + i * entH;
    ctx.fillStyle = colors[i]; ctx.fillRect(lx, ly + entH*0.2, 12, entH*0.6);
    ctx.fillStyle = textCol; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    const pct = showVals ? ` (${Math.round(values[i]/total*100)}%)` : '';
    ctx.fillText(`${lbl}${pct}`, lx + 16, ly + entH/2);
  });
}

function _lightenHex(hex, amount) {
  const n = parseInt(hex.replace('#',''), 16);
  const r = Math.min(255, ((n>>16)&0xff) + amount);
  const g = Math.min(255, ((n>>8)&0xff)  + amount);
  const b = Math.min(255, ( n    &0xff)  + amount);
  return `rgb(${r},${g},${b})`;
}

function _hexToHue(hex) {
  const n = parseInt(hex.replace('#',''), 16);
  const r = ((n>>16)&0xff)/255, g = ((n>>8)&0xff)/255, b = (n&0xff)/255;
  const mx = Math.max(r,g,b), mn = Math.min(r,g,b), d = mx-mn;
  if (d === 0) return 0;
  let h = mx===r ? (g-b)/d%6 : mx===g ? (b-r)/d+2 : (r-g)/d+4;
  return h/6;
}

function _hsvToHex(h, s, v) {
  const i = Math.floor(h*6), f = h*6-i;
  const p=v*(1-s), q=v*(1-f*s), t=v*(1-(1-f)*s);
  let r,g,b;
  switch(i%6){case 0:r=v;g=t;b=p;break;case 1:r=q;g=v;b=p;break;
    case 2:r=p;g=v;b=t;break;case 3:r=p;g=q;b=v;break;
    case 4:r=t;g=p;b=v;break;default:r=v;g=p;b=q;}
  return `#${[r,g,b].map(x=>Math.round(x*255).toString(16).padStart(2,'0')).join('')}`;
}

// ── Diagram renderer (Canvas 2D) ──────────────────────────────────────────────
function _drawPresDiagram(ctx, el, ew, eh, sx) {
  const nodes   = el.nodes    || [];
  const edges   = el.edges    || [];
  const rootCol = el.root_color || '#5294e2';
  const nodeCol = el.node_color || '#1a3a5c';
  const lineCol = el.line_color || '#888888';
  const textCol = el.text_color || '#ffffff';
  const fs      = Math.max(6, Math.round((el.font_size || 18) * (eh / 1080)));

  if (!nodes.length) {
    ctx.fillStyle = textCol; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.font = `${fs}px "Segoe UI", Arial`;
    ctx.fillText('Fără noduri', ew/2, eh/2);
    return;
  }

  const positions = _diagramLayout(nodes, edges, ew, eh);
  const nw = Math.min(ew / 4.5, 160 * (ew / 700));
  const nh = Math.min(eh / 7,   50  * (eh / 450));

  // Edges
  ctx.strokeStyle = lineCol; ctx.lineWidth = Math.max(1, eh * 0.004);
  edges.forEach(([a, b]) => {
    if (!positions[a] || !positions[b]) return;
    const [ax, ay] = positions[a], [bx, by] = positions[b];
    const dx = bx-ax, dy = by-ay, dist = Math.hypot(dx,dy);
    if (dist < 1) return;
    const off = Math.min(nw,nh)/2 + 2;
    const sx2 = ax+dx/dist*off, sy2 = ay+dy/dist*off;
    const ex2 = bx-dx/dist*off, ey2 = by-dy/dist*off;
    ctx.beginPath(); ctx.moveTo(sx2,sy2); ctx.lineTo(ex2,ey2); ctx.stroke();
    const arl = Math.max(8, nh*0.28), ara = 0.4;
    const ang = Math.atan2(ey2-sy2, ex2-sx2);
    ctx.beginPath();
    ctx.moveTo(ex2,ey2);
    ctx.lineTo(ex2 - arl*Math.cos(ang-ara), ey2 - arl*Math.sin(ang-ara));
    ctx.moveTo(ex2,ey2);
    ctx.lineTo(ex2 - arl*Math.cos(ang+ara), ey2 - arl*Math.sin(ang+ara));
    ctx.stroke();
  });

  // Nodes
  ctx.font = `${fs}px "Segoe UI", Arial`;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  positions.forEach(([nx, ny], i) => {
    const col = i === 0 ? rootCol : nodeCol;
    const grad = ctx.createLinearGradient(nx-nw/2, ny-nh/2, nx-nw/2, ny+nh/2);
    grad.addColorStop(0, _lightenHex(col, 30));
    grad.addColorStop(1, col);
    _roundRect(ctx, nx-nw/2, ny-nh/2, nw, nh, 8);
    ctx.fillStyle = grad; ctx.fill();
    ctx.strokeStyle = _lightenHex(col, 60); ctx.lineWidth = Math.max(1, nh*0.04);
    ctx.stroke();
    ctx.fillStyle = textCol;
    ctx.fillText(String(nodes[i] || ''), nx, ny);
  });
}

function _diagramLayout(nodes, edges, w, h) {
  const n = nodes.length;
  if (!n) return [];
  const children = Array.from({length:n}, ()=>[]);
  edges.forEach(([a,b]) => { if(a<n&&b<n) children[a].push(b); });
  const visited = new Array(n).fill(false);
  const levels  = new Array(n).fill(-1);
  let queue = [0]; visited[0] = true; let lv = 0;
  while (queue.length) {
    const next = [];
    queue.forEach(nd => {
      levels[nd] = lv;
      children[nd].forEach(c => { if (!visited[c]) { visited[c]=true; next.push(c); } });
    });
    queue = next; lv++;
  }
  for (let i = 0; i < n; i++) if (!visited[i]) { levels[i] = lv++; }
  const maxLv = Math.max(...levels);
  const byLevel = {};
  levels.forEach((l, i) => { (byLevel[l] = byLevel[l]||[]).push(i); });
  const pad = 40, avH = h - pad*2;
  const lvH = maxLv > 0 ? avH / (maxLv+1) : avH;
  const pos = new Array(n);
  Object.entries(byLevel).forEach(([lvStr, lst]) => {
    const lvi = Number(lvStr);
    const avW = w - pad*2, sp = avW / (lst.length+1);
    const y = pad + lvi*lvH + lvH/2;
    [...lst].sort((a,b)=>a-b).forEach((nd,j) => { pos[nd] = [pad + sp*(j+1), y]; });
  });
  return pos;
}

function _roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x+r, y);
  ctx.lineTo(x+w-r, y); ctx.arcTo(x+w,y, x+w,y+r, r);
  ctx.lineTo(x+w, y+h-r); ctx.arcTo(x+w,y+h, x+w-r,y+h, r);
  ctx.lineTo(x+r, y+h); ctx.arcTo(x,y+h, x,y+h-r, r);
  ctx.lineTo(x, y+r); ctx.arcTo(x,y, x+r,y, r);
  ctx.closePath();
}

// ── Overlays ──────────────────────────────────────────────────────────────────
function drawOverlays(ctx, W, H) {
  drawMetadata(ctx, W, H);
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
  const bold       = ts.bold   ? 'bold '   : '';
  const italic_    = ts.italic ? 'italic ' : '';
  ctx.font         = `${bold}${italic_}${fontSize}px "${fontFamily}"`;
  ctx.fillStyle    = txtCol;
  ctx.textBaseline = 'middle';

  const anim = ts.animation || 'scroll_left';
  let textX  = tickerX;

  if (anim === 'fade') {
    // Slow fade in/out pulse — period scales with speed
    const spd    = parseFloat(ts.speed || 3);
    const period = Math.max(800, 3000 / spd);
    const phase  = (performance.now() % period) / period;
    const alpha  = 0.2 + 0.8 * Math.abs(Math.sin(Math.PI * phase));
    ctx.globalAlpha *= alpha;
    ctx.measureText(state.tickerText); // warm up
    textX  = (W - ctx.measureText(state.tickerText).width) / 2;
    ctx.textAlign = 'left';
  } else if (anim === 'blink') {
    const spd      = parseFloat(ts.speed || 3);
    const blinkHz  = spd * 0.5;
    const visible  = Math.floor(performance.now() * blinkHz / 1000) % 2 === 0;
    if (!visible) { ctx.globalAlpha = savedAlpha; return; }
    textX  = (W - ctx.measureText(state.tickerText).width) / 2;
    ctx.textAlign = 'left';
  } else {
    ctx.textAlign = 'left';
  }

  ctx.save();
  ctx.shadowColor = 'rgba(0,0,0,0.5)';
  ctx.shadowBlur  = 4;
  ctx.beginPath();
  ctx.rect(0, y, W, barH);
  ctx.clip();
  ctx.fillText(state.tickerText, textX, y + barH / 2);
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
  // Custom drag position (set by ClockPositionPicker in settings)
  if (clk.x_pct !== undefined && clk.y_pct !== undefined && position === 'custom') {
    x = W * parseFloat(clk.x_pct);
    y = H * parseFloat(clk.y_pct);
  } else if (position === 'top_left')      { x = pad;                   y = pad + fontSize; }
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
  // Logo opacity follows the manual mixer fader when it's been moved.
  ctx.globalAlpha = state.dim.logo > 0 ? Math.min(1, state.dim.logo) : 0.85;
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
// Paint ONE text-box rect in the chosen style.
function _paintTextBoxRect(ctx, x, y, w, h, radius, style, color, color2, opacity) {
  ctx.save();
  ctx.globalAlpha = opacity;
  ctx.shadowColor = 'transparent'; ctx.shadowBlur = 0;
  switch (style) {
    case 'gradient': {
      const g = ctx.createLinearGradient(x, y, x, y + h);
      g.addColorStop(0, color); g.addColorStop(1, color2 || '#000000');
      ctx.fillStyle = g; roundRect(ctx, x, y, w, h, radius); ctx.fill();
      break;
    }
    case 'outline': {
      ctx.strokeStyle = color; ctx.lineWidth = Math.max(2, h * 0.045);
      roundRect(ctx, x, y, w, h, radius); ctx.stroke();
      break;
    }
    case 'frosted': {
      ctx.fillStyle = color; ctx.globalAlpha = opacity * 0.5;
      roundRect(ctx, x, y, w, h, radius); ctx.fill();
      ctx.globalAlpha = opacity * 0.9; ctx.strokeStyle = 'rgba(255,255,255,0.35)';
      ctx.lineWidth = Math.max(1, h * 0.02);
      roundRect(ctx, x, y, w, h, radius); ctx.stroke();
      break;
    }
    case 'shadow': {
      ctx.shadowColor = 'rgba(0,0,0,0.55)'; ctx.shadowBlur = h * 0.25;
      ctx.shadowOffsetX = 0; ctx.shadowOffsetY = h * 0.08;
      ctx.fillStyle = color; roundRect(ctx, x, y, w, h, radius); ctx.fill();
      break;
    }
    case 'underline': {
      const bh = Math.max(3, h * 0.10);
      ctx.fillStyle = color; roundRect(ctx, x, y + h - bh, w, bh, bh / 2); ctx.fill();
      break;
    }
    case 'sketch': {
      // Hand-drawn double outline (two slightly offset rounded rects)
      ctx.strokeStyle = color; ctx.lineWidth = Math.max(2, h * 0.04);
      ctx.lineJoin = 'round'; ctx.lineCap = 'round';
      roundRect(ctx, x, y, w, h, radius); ctx.stroke();
      ctx.save(); ctx.translate(2.5, -2); ctx.globalAlpha = opacity * 0.6;
      roundRect(ctx, x, y, w, h, radius + 3); ctx.stroke(); ctx.restore();
      break;
    }
    default: { // solid
      ctx.fillStyle = color; roundRect(ctx, x, y, w, h, radius); ctx.fill();
      break;
    }
  }
  ctx.restore();
}

function drawTextBox(lines, lineH, startY, ctx, W, H, s, currentSize, align, baseX) {
  const boxColor  = s.text_box_color   || '#000000';
  const boxColor2 = s.text_box_color2  || '#1a1a1a';
  const opacity   = parseFloat(s.text_box_opacity  ?? 0.6);
  const padH      = parseInt(s.text_box_padding_h  ?? 20);
  const padV      = parseInt(s.text_box_padding_v  ?? 12);
  const radius    = parseInt(s.text_box_radius     ?? 8);
  const fit       = s.text_box_fit     || 'per_line';
  const style     = s.text_box_style   || 'solid';
  const paint = (x, y, w, h, r) =>
    _paintTextBoxRect(ctx, x, y, w, h, r, style, boxColor, boxColor2, opacity);

  if (fit === 'full_block') {
    let maxLineW = 0;
    lines.forEach(line => {
      if (!line) return;
      const lw = ctx.measureText(line).width;
      if (lw > maxLineW) maxLineW = lw;
    });
    const bx = (align === 'left'  ? baseX - padH
              : align === 'right' ? baseX - maxLineW - padH
              : baseX - maxLineW / 2 - padH);
    const by = startY - currentSize * 0.85 - padV;
    paint(bx, by, maxLineW + padH * 2, lineH * lines.length + padV * 2, radius);
  } else if (fit === 'full_width') {
    lines.forEach((line, i) => {
      if (!line) return;
      const by = startY + i * lineH - currentSize * 0.85 - padV;
      paint(0, by, W, currentSize + padV * 2, 0);
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
      paint(bx, by, lw + padH * 2, currentSize + padV * 2, radius);
    });
  }
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
    const anim     = tickerSettings.animation || 'scroll_left';
    if (anim === 'scroll_left' || anim === 'scroll_right') {
      const dir  = anim === 'scroll_right' ? 1 : -1;
      tickerX   += dir * pxPerSec * dt / 1000;
      const textW = (ctxC ? ctxC.measureText(state.tickerText).width : 0) || cvCurr.width;
      if (anim === 'scroll_left'  && tickerX < -textW - 50)      tickerX = cvCurr.width + 50;
      if (anim === 'scroll_right' && tickerX > cvCurr.width + 50) tickerX = -textW - 50;
    }
    // fade and blink don't advance position — they pulse in drawTicker
    needRedraw = true;
  }

  if (state.clockActive || state.timerActive) needRedraw = true;

  // Chaotic text movement / animated text colour need continuous redraw
  const _s = state.settings;
  if (state.text && (_s.text_chaos === 'true' || _s.text_chaos === true ||
                     _s.text_color_type === 'animated')) {
    needRedraw = true;
  }

  if (needRedraw && !transition.active) renderCurrent();

  requestAnimationFrame(mainLoop);
}
