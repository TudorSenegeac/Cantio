/* Cantio — Background Editor (renderer logic) */
'use strict';

// Node access is available under Electron (nodeIntegration); guard so the page
// also opens harmlessly in a plain browser preview.
const _fs   = (typeof require !== 'undefined') ? require('fs')   : null;
let   _ipc  = null;
try { _ipc = (typeof require !== 'undefined') ? require('electron').ipcRenderer : null; } catch (e) {}

const ICONS = { gradient:'🌈', particles:'✨', shape:'⬛', text:'🅣', clock:'🕐', lyrics:'🎤', image:'🖼', video:'🎬' };

const state = {
  bg: null,
  file: new URLSearchParams(location.search).get('file') || '',
  selId: null,
  playing: true,
  t0: performance.now(),
  tHold: 0,
  // Multi-slide (song) mode
  multi: false,
  wrapper: null,    // { format, name, slides:[ bg-doc, ... ] }
  slideIdx: 0,
  rulers: true,     // rulers + centre guides + snap-to-centre
};

const $ = (id) => document.getElementById(id);
const canvas = $('preview');
const ctx = canvas.getContext('2d');

// ── Load / Save ───────────────────────────────────────────────────────────────

function _blankSlide(fmt) {
  return { format: { w: fmt.w, h: fmt.h }, layers: [] };
}
function _normSlide(s, fmt) {
  if (!s.format) s.format = { w: fmt.w, h: fmt.h };
  if (!Array.isArray(s.layers)) s.layers = [];
}

function loadBg() {
  let doc = null;
  if (_fs && state.file) {
    try {
      doc = JSON.parse(_fs.readFileSync(state.file, 'utf-8'));
    } catch (e) { console.warn('[Editor] load failed:', e.message); }
  }
  if (doc && Array.isArray(doc.slides)) {
    // ── Multi-slide (song) mode ──
    state.multi = true;
    state.wrapper = doc;
    if (!doc.format) doc.format = { w: 1920, h: 1080 };
    if (!doc.slides.length) doc.slides.push(_blankSlide(doc.format));
    doc.slides.forEach(s => _normSlide(s, doc.format));
    state.slideIdx = 0;
    state.bg = doc.slides[0];
    state.bg.format = doc.format;
  } else {
    // ── Single background (Fundal) mode ──
    state.multi = false;
    state.bg = doc || BgEngine.defaultBackground();
    if (!state.bg.format) state.bg.format = { w: 1920, h: 1080 };
    if (!Array.isArray(state.bg.layers)) state.bg.layers = [];
  }
}

function saveBg() {
  if (!_fs || !state.file) { flash('Salvare indisponibilă (fără fișier)'); return; }
  try {
    const stripper = (k, v) => (k.startsWith('_') ? undefined : v);
    let payload;
    if (state.multi) {
      state.wrapper.name = $('bgName').value || state.wrapper.name || 'Cântare';
      payload = state.wrapper;
    } else {
      state.bg.name = $('bgName').value || state.bg.name || 'Fundal';
      payload = state.bg;
    }
    const clean = JSON.parse(JSON.stringify(payload, stripper));
    _fs.writeFileSync(state.file, JSON.stringify(clean, null, 2), 'utf-8');
    writeThumbnail();
    flash('✓ Salvat');
    if (_ipc) { try { _ipc.send('bg_saved', state.file); } catch (e) {} }
  } catch (e) { flash('Eroare salvare: ' + e.message); }
}

function writeThumbnail() {
  if (!_fs || !state.file) return;
  try {
    const tw = 384, th = Math.round(384 * canvas.height / canvas.width);
    const tc = document.createElement('canvas');
    tc.width = tw; tc.height = th;
    // Render a CLEAN frame (no selection handles / rulers / guides) so they
    // never end up baked into the saved thumbnail.
    const tctx = tc.getContext('2d');
    try {
      const tt = state.playing ? (performance.now() - state.t0) : state.tHold;
      BgEngine.render(tctx, tw, th, state.bg, tt, 1);
    } catch (e) {
      tctx.drawImage(canvas, 0, 0, tw, th);
    }
    const b64 = tc.toDataURL('image/jpeg', 0.82).split(',')[1];
    _fs.writeFileSync(state.file.replace(/\.json$/i, '.jpg'),
                      Buffer.from(b64, 'base64'));
  } catch (e) { /* thumbnail is best-effort */ }
}

let _flashTO = null;
function flash(msg) {
  const b = $('saveBtn'); const old = b.textContent;
  b.textContent = msg; clearTimeout(_flashTO);
  _flashTO = setTimeout(() => { b.textContent = '💾 Salvează'; }, 1400);
}

// ── Format / canvas sizing ──────────────────────────────────────────────────

function applyFormat() {
  const f = state.bg.format;
  canvas.width = f.w; canvas.height = f.h;
  $('resLabel').textContent = `${f.w}×${f.h}`;
  // sync selector
  const key = `${f.w}x${f.h}`;
  const sel = $('formatSel');
  const known = Array.from(sel.options).some(o => o.value === key);
  sel.value = known ? key : 'custom';
  const custom = !known;
  $('customW').style.display = custom ? '' : 'none';
  $('customH').style.display = custom ? '' : 'none';
  $('customW').value = f.w; $('customH').value = f.h;
  fitCanvas();
}

function fitCanvas() {
  const stage = canvas.parentElement.parentElement; // .stage
  const pad = 32;
  const aw = stage.clientWidth - pad, ah = stage.clientHeight - pad;
  const ar = canvas.width / canvas.height;
  let w = aw, h = aw / ar;
  if (h > ah) { h = ah; w = ah * ar; }
  const wrap = $('canvasWrap');
  wrap.style.width = w + 'px'; wrap.style.height = h + 'px';
  canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
}
window.addEventListener('resize', fitCanvas);

// ── Slides rail (multi-slide / song mode) ────────────────────────────────────

function _renderSlideThumb(slide, tw, th) {
  const c = document.createElement('canvas');
  c.width = tw; c.height = th;
  try { BgEngine.render(c.getContext('2d'), tw, th, slide, 0, 1); } catch (e) {}
  return c;
}

function rebuildSlides() {
  if (!state.multi) return;
  const list = $('slideList');
  list.innerHTML = '';
  const f = state.wrapper.format;
  const tw = 140, th = Math.round(140 * f.h / f.w);
  state.wrapper.slides.forEach((slide, i) => {
    const div = document.createElement('div');
    div.className = 'slide-thumb' + (i === state.slideIdx ? ' sel' : '');
    div.appendChild(_renderSlideThumb(slide, tw, th));
    const num = document.createElement('span'); num.className = 'num'; num.textContent = (i + 1);
    div.appendChild(num);
    const del = document.createElement('button'); del.className = 'del'; del.textContent = '🗑';
    del.onclick = (e) => { e.stopPropagation(); delSlide(i); };
    div.appendChild(del);
    div.onclick = () => switchSlide(i);
    // right-click → duplicate
    div.oncontextmenu = (e) => { e.preventDefault(); dupSlide(i); };
    list.appendChild(div);
  });
}

function switchSlide(idx) {
  if (!state.multi || idx < 0 || idx >= state.wrapper.slides.length) return;
  state.slideIdx = idx;
  state.bg = state.wrapper.slides[idx];
  state.bg.format = state.wrapper.format;
  state.selId = null;
  rebuildSlides(); rebuildLayers(); rebuildProps();
}

function addSlide() {
  if (!state.multi) return;
  state.wrapper.slides.push(_blankSlide(state.wrapper.format));
  switchSlide(state.wrapper.slides.length - 1);
}

function dupSlide(idx) {
  if (!state.multi) return;
  const copy = JSON.parse(JSON.stringify(state.wrapper.slides[idx], (k, v) =>
    (k.startsWith('_') ? undefined : v)));
  // fresh ids for layers
  (copy.layers || []).forEach(l => { l.id = BgEngine.uid(); });
  state.wrapper.slides.splice(idx + 1, 0, copy);
  switchSlide(idx + 1);
}

function delSlide(idx) {
  if (!state.multi || state.wrapper.slides.length <= 1) return;
  state.wrapper.slides.splice(idx, 1);
  state.slideIdx = Math.max(0, Math.min(state.slideIdx, state.wrapper.slides.length - 1));
  switchSlide(state.slideIdx);
}

// ── Render loop ──────────────────────────────────────────────────────────────

function buildBackgroundSettings(p) {
  const bg = state.bg;
  if (bg.intro_stagger == null) bg.intro_stagger = 350;
  if (!bg.transition) bg.transition = { in: 'fade', out: 'fade', duration: 600 };
  const hint = document.createElement('div');
  hint.className = 'empty';
  hint.style.padding = '8px 0';
  hint.textContent = 'Niciun layer selectat — setări fundal:';
  p.appendChild(hint);

  grpH(p, 'INTRARE SECVENȚIALĂ');
  p.appendChild(row('Activă', mkCheck(bg, 'intro_sequence')));
  p.appendChild(row('Decalaj (ms)', mkRange(bg, 'intro_stagger', 0, 2000, 50)));
  const seqHint = document.createElement('div');
  seqHint.style.cssText = 'color:#6c7086;font-size:10px;margin:2px 0 6px';
  seqHint.textContent = 'Layerele intră pe rând, de jos în sus.';
  p.appendChild(seqHint);
  const inBtn = document.createElement('button'); inBtn.className = 'btn';
  inBtn.textContent = '▶ Preview intrare (tot)'; inBtn.onclick = () => previewPhase('intro');
  p.appendChild(row('', inBtn));
  const outBtn = document.createElement('button'); outBtn.className = 'btn';
  outBtn.textContent = '▶ Preview ieșire (tot)'; outBtn.onclick = () => previewPhase('outro');
  p.appendChild(row('', outBtn));

  grpH(p, 'TRANZIȚIE ÎNTRE FUNDALURI');
  p.appendChild(row('Durată (ms)', mkRange(bg.transition, 'duration', 100, 2000, 50)));

  // ── Background base: pick a saved Fundal, or add a gradient/solid base ──────
  grpH(p, 'FUNDAL DE BAZĂ');
  const files = listBackgrounds();
  const sel = document.createElement('select');
  const ph = document.createElement('option');
  ph.value = ''; ph.textContent = files.length ? '— Alege fundal salvat —' : '(niciun fundal salvat)';
  sel.appendChild(ph);
  files.forEach(f => {
    const o = document.createElement('option');
    o.value = f; o.textContent = f.replace(/\.json$/i, '');
    sel.appendChild(o);
  });
  sel.onchange = () => { if (sel.value) { insertBaseBackground(sel.value); sel.value = ''; } };
  p.appendChild(row('Din Fundal', sel));

  const gBtn = document.createElement('button'); gBtn.className = 'btn';
  gBtn.textContent = '+ Gradient de bază';
  gBtn.onclick = () => { addBaseLayer('gradient'); };
  p.appendChild(row('', gBtn));
  const sBtn = document.createElement('button'); sBtn.className = 'btn';
  sBtn.textContent = '+ Culoare plină';
  sBtn.onclick = () => { addBaseLayer('shape'); };
  p.appendChild(row('', sBtn));
  const hintB = document.createElement('div');
  hintB.style.cssText = 'color:#6c7086;font-size:10px;margin:4px 0';
  hintB.textContent = 'Baza se adaugă în spatele celorlalte layere.';
  p.appendChild(hintB);
}

// ── Background base helpers ───────────────────────────────────────────────────
function _bgFolder() {
  try {
    const path = require('path'), os = require('os'), fs = require('fs');
    // Per-profile backgrounds — read the active profile the app wrote out.
    let prof = 'Default';
    try {
      const pf = path.join(os.homedir(), 'Cantio', '.active_profile');
      if (fs.existsSync(pf)) prof = (fs.readFileSync(pf, 'utf-8') || 'Default').trim() || 'Default';
    } catch (e) {}
    const dir = path.join(os.homedir(), 'Cantio', 'profiles', prof, 'backgrounds');
    try { fs.mkdirSync(dir, { recursive: true }); } catch (e) {}
    return dir;
  } catch (e) { return null; }
}
function listBackgrounds() {
  const dir = _bgFolder();
  if (!dir || !_fs) return [];
  try { return _fs.readdirSync(dir).filter(f => /\.json$/i.test(f)).sort(); }
  catch (e) { return []; }
}
function insertBaseBackground(file) {
  const dir = _bgFolder(); if (!dir || !_fs) return;
  try {
    const doc = JSON.parse(_fs.readFileSync(require('path').join(dir, file), 'utf-8'));
    let layers = Array.isArray(doc.layers) ? doc.layers
               : (doc.slides && doc.slides[0] && doc.slides[0].layers) || [];
    if (!layers.length) { flash('Fundalul nu are layere'); return; }
    // Clone with fresh ids and insert at the BOTTOM (behind the text/lyrics).
    const cloned = JSON.parse(JSON.stringify(layers)).map(L => { L.id = BgEngine.uid(); return L; });
    state.bg.layers.unshift(...cloned);
    rebuildLayers(); rebuildProps();
    flash('✓ Fundal adăugat ca bază');
  } catch (e) { flash('Eroare fundal: ' + e.message); }
}
function addBaseLayer(type) {
  const L = BgEngine.newLayer(type);
  if (type === 'shape') { L.shape = 'rect'; L.w = 1; L.h = 1; L.x = 0.5; L.y = 0.5; L.name = 'Fundal plin'; }
  state.bg.layers.unshift(L);   // bottom of the stack
  selectLayer(L.id);
}

// Visual background picker (thumbnails of saved Fundal backgrounds + quick base).
function openBgPicker() {
  const files = listBackgrounds();
  const dir = _bgFolder();
  const back = document.createElement('div');
  back.style.cssText = 'position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,0.62);' +
    'display:flex;align-items:center;justify-content:center;';
  const panel = document.createElement('div');
  panel.style.cssText = 'background:#16161e;border:1px solid #2a2a3a;border-radius:10px;' +
    'padding:16px;max-width:84vw;max-height:84vh;overflow:auto;box-shadow:0 12px 48px rgba(0,0,0,.6);';
  const h = document.createElement('div');
  h.textContent = 'Alege fundal de bază';
  h.style.cssText = 'color:#e6e6ee;font-size:15px;font-weight:600;margin-bottom:12px;';
  panel.appendChild(h);
  const grid = document.createElement('div');
  grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));' +
    'gap:10px;width:66vw;';

  const close = () => { if (back.parentNode) document.body.removeChild(back); };
  const mkCard = (label, thumbCss, onClick) => {
    const card = document.createElement('div');
    card.style.cssText = 'cursor:pointer;border:1px solid #2a2a3a;border-radius:8px;' +
      'overflow:hidden;background:#0e0e14;transition:border-color .12s;';
    const th = document.createElement('div');
    th.style.cssText = 'height:96px;' + thumbCss;
    const nm = document.createElement('div');
    nm.textContent = label;
    nm.style.cssText = 'padding:6px 8px;color:#c6c6d2;font-size:11px;white-space:nowrap;' +
      'overflow:hidden;text-overflow:ellipsis;';
    card.appendChild(th); card.appendChild(nm);
    card.onmouseenter = () => { card.style.borderColor = '#5294e2'; };
    card.onmouseleave = () => { card.style.borderColor = '#2a2a3a'; };
    card.onclick = () => { onClick(); close(); };
    return card;
  };

  grid.appendChild(mkCard('+ Gradient de bază',
    'background:linear-gradient(135deg,#1a237e,#3949ab,#0d47a1);',
    () => addBaseLayer('gradient')));
  grid.appendChild(mkCard('+ Culoare plină',
    'background:#23232b;', () => addBaseLayer('shape')));
  files.forEach((f) => {
    const jpg = 'file:///' + ((dir || '') + '/' + f.replace(/\.json$/i, '.jpg')).replace(/\\/g, '/');
    grid.appendChild(mkCard(f.replace(/\.json$/i, ''),
      `background:#000 center/cover no-repeat url("${jpg}");`,
      () => insertBaseBackground(f)));
  });
  if (!files.length) {
    const e = document.createElement('div');
    e.textContent = 'Niciun fundal salvat în tab-ul Fundal încă.';
    e.style.cssText = 'grid-column:1/-1;color:#6c7086;font-size:11px;padding:4px;';
    grid.appendChild(e);
  }
  panel.appendChild(grid);

  const cancel = document.createElement('button');
  cancel.className = 'btn'; cancel.textContent = 'Închide';
  cancel.style.marginTop = '12px'; cancel.onclick = close;
  panel.appendChild(cancel);
  back.appendChild(panel);
  back.onclick = (e) => { if (e.target === back) close(); };
  document.body.appendChild(back);
}

function previewPhase(kind) {
  // Play the entrance ('intro') or exit ('outro') once so the user sees it.
  state.phaseKind = kind;
  state.phaseStart = performance.now();
  // longest (stagger + delay + duration) across layers, so the whole sequence shows
  let maxMs = 800;
  state.bg.layers.forEach((L, i) => {
    const e = (kind === 'intro' ? L.entrance : L.exit) || {};
    if (e.type && e.type !== 'none') {
      const extra = (kind === 'intro' && state.bg.intro_sequence)
        ? i * (state.bg.intro_stagger || 350) : 0;
      maxMs = Math.max(maxMs, extra + (e.delay || 0) + (e.duration || 600) + 300);
    }
  });
  state.phaseMax = maxMs;
}

let _lastThumbT = 0;
function _updateCurrentThumb(t) {
  const list = $('slideList');
  if (!list) return;
  const div = list.children[state.slideIdx];
  if (!div) return;
  const c = div.querySelector('canvas');
  if (!c) return;
  try { BgEngine.render(c.getContext('2d'), c.width, c.height, state.bg, t, 1); } catch (e) {}
}

function renderLoop() {
  const t = state.playing ? (performance.now() - state.t0) : state.tHold;
  let opts = 1;
  if (state.phaseKind) {
    const dt = performance.now() - state.phaseStart;
    if (dt >= state.phaseMax) { state.phaseKind = null; }
    else opts = (state.phaseKind === 'intro') ? { intro: dt } : { outro: dt };
  }
  // Hide the layer being inline-edited so the canvas text doesn't ghost behind
  // the editing textarea (restored right after the render — never saved).
  const editL = inlineEditLayer();
  let _savedOp;
  if (editL) { _savedOp = editL.opacity; editL.opacity = 0; }
  BgEngine.render(ctx, canvas.width, canvas.height, state.bg, t, opts);
  if (editL) editL.opacity = _savedOp;
  drawSelectionOverlay();
  // Keep the current slide's thumbnail roughly live (~2 fps, cheap)
  if (state.multi && performance.now() - _lastThumbT > 500) {
    _lastThumbT = performance.now();
    _updateCurrentThumb(t);
  }
  requestAnimationFrame(renderLoop);
}

// ── Direct-manipulation: select / move / resize on the canvas ─────────────────

const SELECTABLE = { shape: 1, text: 1, clock: 1, image: 1, video: 1, lyrics: 1 };
let drag = null;

function isSelectable(L) { return L && SELECTABLE[L.type] && L.visible !== false; }

function evToCanvas(e) {
  const r = canvas.getBoundingClientRect();
  return {
    x: (e.clientX - r.left) / r.width  * canvas.width,
    y: (e.clientY - r.top)  / r.height * canvas.height,
  };
}

function layerBox(L) {
  const W = canvas.width, H = canvas.height;
  const bw = (L.w != null ? L.w : 0.3) * W;
  const bh = (L.h != null ? L.h : 0.3) * H;
  const cx = (L.x != null ? L.x : 0.5) * W;
  const cy = (L.y != null ? L.y : 0.5) * H;
  return { cx, cy, bw, bh, x0: cx - bw / 2, y0: cy - bh / 2, x1: cx + bw / 2, y1: cy + bh / 2 };
}

function handlePoints(b) {
  return {
    nw: [b.x0, b.y0], n: [b.cx, b.y0], ne: [b.x1, b.y0],
    w:  [b.x0, b.cy],                  e:  [b.x1, b.cy],
    sw: [b.x0, b.y1], s: [b.cx, b.y1], se: [b.x1, b.y1],
  };
}

function handleAt(pt, b) {
  const hr = Math.max(16, canvas.width * 0.014);
  const pts = handlePoints(b);
  for (const k in pts) {
    if (Math.abs(pt.x - pts[k][0]) <= hr && Math.abs(pt.y - pts[k][1]) <= hr) return k;
  }
  return null;
}

function topmostAt(pt) {
  for (let i = state.bg.layers.length - 1; i >= 0; i--) {
    const L = state.bg.layers[i];
    if (!isSelectable(L)) continue;
    const b = layerBox(L);
    if (pt.x >= b.x0 && pt.x <= b.x1 && pt.y >= b.y0 && pt.y <= b.y1) return L;
  }
  return null;
}

canvas.addEventListener('mousedown', (e) => {
  const pt = evToCanvas(e);
  const sel = selectedLayer();
  if (isSelectable(sel)) {
    const k = handleAt(pt, layerBox(sel));
    if (k) { drag = { mode: 'resize', key: k, box0: layerBox(sel), size0: sel.size }; return; }
    const b = layerBox(sel);
    if (pt.x >= b.x0 && pt.x <= b.x1 && pt.y >= b.y0 && pt.y <= b.y1) {
      drag = { mode: 'move', box0: b, m0: pt }; return;
    }
  }
  const hit = topmostAt(pt);
  if (hit) {
    selectLayer(hit.id);
    drag = { mode: 'move', box0: layerBox(hit), m0: pt };
  } else {
    state.selId = null; rebuildLayers(); rebuildProps();
  }
});

window.addEventListener('mousemove', (e) => {
  if (!drag) { updateCursor(e); return; }
  const sel = selectedLayer(); if (!sel) return;
  const pt = evToCanvas(e);
  const W = canvas.width, H = canvas.height;

  if (drag.mode === 'move') {
    sel.x = (drag.box0.cx + (pt.x - drag.m0.x)) / W;
    sel.y = (drag.box0.cy + (pt.y - drag.m0.y)) / H;
    // Snap to canvas centre (unless Alt is held to move freely)
    if (!e.altKey) {
      if (Math.abs(sel.x - 0.5) < SNAP) sel.x = 0.5;
      if (Math.abs(sel.y - 0.5) < SNAP) sel.y = 0.5;
    }
  } else {
    const k = drag.key;
    let { x0, y0, x1, y1 } = drag.box0;
    if (k.includes('w')) x0 = pt.x;
    if (k.includes('e')) x1 = pt.x;
    if (k.includes('n')) y0 = pt.y;
    if (k.includes('s')) y1 = pt.y;
    const minW = 24, minH = 24;
    if (x1 - x0 < minW) { if (k.includes('w')) x0 = x1 - minW; else x1 = x0 + minW; }
    if (y1 - y0 < minH) { if (k.includes('n')) y0 = y1 - minH; else y1 = y0 + minH; }
    const nh = y1 - y0;
    sel.x = ((x0 + x1) / 2) / W; sel.y = ((y0 + y1) / 2) / H;
    sel.w = (x1 - x0) / W; sel.h = nh / H;
    if ((sel.type === 'text' || sel.type === 'clock') && drag.size0 && drag.box0.bh > 0)
      sel.size = Math.max(8, Math.round(drag.size0 * (nh / drag.box0.bh)));
  }
});

window.addEventListener('mouseup', () => {
  if (drag) { drag = null; rebuildProps(); }   // sync sliders after manipulation
});

// ── Inline text editing (double-click the text on the canvas) ─────────────────
// Real, directly-editable text: a textarea is overlaid exactly on the layer's
// box with matching font/size, and writes straight back to L.text.
let _inlineEl = null;
function inlineEditLayer() { return _inlineEl ? selectedLayer() : null; }

function startInlineEdit(L) {
  if (!L || L.type !== 'text') return;
  finishInlineEdit();
  const rect = canvas.getBoundingClientRect();
  const b = layerBox(L);
  const sx = rect.left + (b.x0 / canvas.width)  * rect.width;
  const sy = rect.top  + (b.y0 / canvas.height) * rect.height;
  const sw = (b.bw / canvas.width)  * rect.width;
  const sh = (b.bh / canvas.height) * rect.height;
  const fontPx = (L.size || 96) * (rect.height / canvas.height);
  const ta = document.createElement('textarea');
  _inlineEl = ta;
  ta.value = L.text || '';
  ta.spellcheck = false;
  ta.style.cssText =
    'position:fixed;z-index:9999;box-sizing:border-box;padding:2px 6px;' +
    'background:rgba(10,12,20,0.92);color:#fff;border:2px solid #5294e2;' +
    'border-radius:6px;outline:none;resize:none;overflow:hidden;';
  ta.style.left = sx + 'px'; ta.style.top = sy + 'px';
  ta.style.width = Math.max(80, sw) + 'px';
  ta.style.height = Math.max(40, sh) + 'px';
  ta.style.textAlign = L.align || 'center';
  ta.style.font = (L.italic ? 'italic ' : '') + (L.bold ? '700 ' : '400 ') +
                  fontPx + 'px "' + (L.font || 'Montserrat') + '", Arial, sans-serif';
  ta.style.lineHeight = (L.lineHeight || 1.15);
  document.body.appendChild(ta);
  ta.focus(); ta.select();
  ta.addEventListener('input', () => { const s = selectedLayer(); if (s) s.text = ta.value; });
  ta.addEventListener('blur', finishInlineEdit);
  ta.addEventListener('keydown', (ev) => {
    ev.stopPropagation();
    if (ev.key === 'Escape' || (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey))) {
      ev.preventDefault(); finishInlineEdit();
    }
  });
}
function finishInlineEdit() {
  if (!_inlineEl) return;
  const ta = _inlineEl; _inlineEl = null;
  const L = selectedLayer();
  if (L) L.text = ta.value;
  ta.remove();
  rebuildProps();
}

canvas.addEventListener('dblclick', (e) => {
  const pt = evToCanvas(e);
  const hit = topmostAt(pt);
  if (hit && hit.type === 'text') { selectLayer(hit.id); startInlineEdit(hit); }
});

function updateCursor(e) {
  const pt = evToCanvas(e);
  const sel = selectedLayer();
  if (isSelectable(sel)) {
    const k = handleAt(pt, layerBox(sel));
    const cur = { nw: 'nwse-resize', se: 'nwse-resize', ne: 'nesw-resize', sw: 'nesw-resize',
                  n: 'ns-resize', s: 'ns-resize', e: 'ew-resize', w: 'ew-resize' };
    if (k) { canvas.style.cursor = cur[k]; return; }
  }
  canvas.style.cursor = topmostAt(pt) ? 'move' : 'default';
}

// Snap threshold (normalised): when a layer's centre/edge is this close to the
// canvas centre, dragging snaps to it. Also drives the "centred" guide glow.
const SNAP = 0.012;

function drawRulers() {
  if (!state.rulers) return;
  const W = canvas.width, H = canvas.height;
  ctx.save();
  // Edge rulers: tick marks every 10% with a longer/centre tick at 50%.
  ctx.fillStyle = 'rgba(255,255,255,0.45)';
  ctx.strokeStyle = 'rgba(255,255,255,0.30)';
  ctx.lineWidth = Math.max(1, W * 0.0008);
  const major = Math.max(10, W * 0.012);   // tick length at centre
  const minor = major * 0.5;
  for (let i = 0; i <= 10; i++) {
    const len = (i === 5) ? major : minor;
    const x = (i / 10) * W, y = (i / 10) * H;
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, len); ctx.stroke();           // top
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(len, y); ctx.stroke();           // left
  }
  ctx.restore();
}

function drawCenterGuides(L) {
  const W = canvas.width, H = canvas.height;
  const onX = Math.abs((L.x != null ? L.x : 0.5) - 0.5) < SNAP;
  const onY = Math.abs((L.y != null ? L.y : 0.5) - 0.5) < SNAP;
  ctx.save();
  ctx.lineWidth = Math.max(1, W * 0.001);
  ctx.setLineDash([10, 8]);
  // Vertical centre line
  ctx.strokeStyle = onX ? 'rgba(255,80,120,0.9)' : 'rgba(255,255,255,0.18)';
  ctx.beginPath(); ctx.moveTo(W / 2, 0); ctx.lineTo(W / 2, H); ctx.stroke();
  // Horizontal centre line
  ctx.strokeStyle = onY ? 'rgba(255,80,120,0.9)' : 'rgba(255,255,255,0.18)';
  ctx.beginPath(); ctx.moveTo(0, H / 2); ctx.lineTo(W, H / 2); ctx.stroke();
  ctx.restore();
}

function drawSelectionOverlay() {
  drawRulers();
  const L = selectedLayer();
  if (!isSelectable(L)) return;
  // Centre guides only while something is selected (or dragged).
  if (state.rulers || drag) drawCenterGuides(L);
  const b = layerBox(L);
  const s = Math.max(7, canvas.width * 0.006);   // handle half-size
  ctx.save();
  ctx.setLineDash([8, 6]);
  ctx.lineWidth = Math.max(1.5, canvas.width * 0.0016);
  ctx.strokeStyle = '#5294e2';
  ctx.strokeRect(b.x0, b.y0, b.bw, b.bh);
  ctx.setLineDash([]);
  ctx.fillStyle = '#ffffff';
  ctx.strokeStyle = '#5294e2';
  const pts = handlePoints(b);
  for (const k in pts) {
    ctx.beginPath();
    ctx.rect(pts[k][0] - s, pts[k][1] - s, s * 2, s * 2);
    ctx.fill(); ctx.stroke();
  }
  ctx.restore();
}

// ── Layers list ──────────────────────────────────────────────────────────────

function rebuildLayers() {
  const list = $('layersList');
  list.innerHTML = '';
  // top layer first in the list (reverse paint order)
  const layers = state.bg.layers;
  layers.forEach(ensureLayerMedia);   // make sure image/video layers are loaded
  for (let i = layers.length - 1; i >= 0; i--) {
    const L = layers[i];
    const item = document.createElement('div');
    item.className = 'layer-item' + (L.id === state.selId ? ' sel' : '');
    item.innerHTML =
      `<span class="ico">${ICONS[L.type] || '▪'}</span>` +
      `<span class="lname">${escapeHtml(L.name || L.type)}</span>` +
      `<button class="mini" data-act="vis" title="Vizibil">${L.visible === false ? '🚫' : '👁'}</button>` +
      `<button class="mini" data-act="up" title="Sus">▲</button>` +
      `<button class="mini" data-act="down" title="Jos">▼</button>` +
      `<button class="mini" data-act="del" title="Șterge">🗑</button>`;
    item.addEventListener('click', (e) => {
      const act = e.target.getAttribute && e.target.getAttribute('data-act');
      if (act === 'vis')  { L.visible = !(L.visible !== false); rebuildLayers(); }
      else if (act === 'up')   { moveLayer(i, +1); }
      else if (act === 'down') { moveLayer(i, -1); }
      else if (act === 'del')  { delLayer(i); }
      else { selectLayer(L.id); }
    });
    list.appendChild(item);
  }
}

function moveLayer(i, dir) {
  const layers = state.bg.layers;
  const j = i + dir;
  if (j < 0 || j >= layers.length) return;
  const tmp = layers[i]; layers[i] = layers[j]; layers[j] = tmp;
  rebuildLayers();
}

function delLayer(i) {
  const L = state.bg.layers[i];
  state.bg.layers.splice(i, 1);
  if (state.selId === L.id) { state.selId = null; rebuildProps(); }
  rebuildLayers();
}

function selectLayer(id) { state.selId = id; rebuildLayers(); rebuildProps(); }

function addLayer(type) {
  if (!type) return;   // guard: never create a typeless ("null") layer
  const L = BgEngine.newLayer(type);
  state.bg.layers.push(L);
  selectLayer(L.id);
  if (type === 'image' || type === 'video') pickMedia(L);
}

// ── Properties panel ─────────────────────────────────────────────────────────

function selectedLayer() {
  return state.bg.layers.find(l => l.id === state.selId) || null;
}

function normalizeLayer(L) {
  // Backfill nested objects so the props panel never hits an undefined.
  if (!L.shadow) L.shadow = { enabled: false, color: '#000000', blur: 18, x: 0, y: 8 };
  if (L.blur == null) L.blur = 0;
  if (L.opacity == null) L.opacity = 1;
  if (!L.anim) L.anim = {};
  if (!L.entrance) L.entrance = { type: 'fade', duration: 700, delay: 0 };
  if (!L.exit)     L.exit     = { type: 'fade', duration: 500, delay: 0 };
  if (L.type === 'text' && !L.echo)
    L.echo = { enabled: false, scale: 2.4, opacity: 0.14, blur: 2 };
  if (L.type === 'gradient' && !L.animate)
    L.animate = { mode: 'none', speed: 0.4 };
  if (L.type === 'gradient' && !Array.isArray(L.stops))
    L.stops = [{ pos: 0, color: '#1a237e' }, { pos: 1, color: '#0d47a1' }];
}

function rebuildProps() {
  const p = $('propsPanel');
  p.innerHTML = '';
  const L = selectedLayer();
  if (!L) { buildBackgroundSettings(p); return; }
  normalizeLayer(L);

  grpH(p, (L.type || '').toUpperCase());
  p.appendChild(row('Nume', mkText(L, 'name', rebuildLayers)));

  if (L.type === 'gradient') buildGradientProps(p, L);
  else if (L.type === 'particles') buildParticleProps(p, L);
  else if (L.type === 'shape') buildShapeProps(p, L);
  else if (L.type === 'text') buildTextProps(p, L);
  else if (L.type === 'clock') buildClockProps(p, L);
  else if (L.type === 'lyrics') buildLyricsProps(p, L);
  else if (L.type === 'image' || L.type === 'video') buildMediaProps(p, L);

  // Common: position/size (skip for full-bleed gradient/particles)
  if (L.type !== 'gradient' && L.type !== 'particles') {
    grpH(p, 'POZIȚIE & MĂRIME');
    p.appendChild(row('X %',  mkRange(L, 'x', 0, 1, 0.01)));
    p.appendChild(row('Y %',  mkRange(L, 'y', 0, 1, 0.01)));
    p.appendChild(row('Lățime', mkRange(L, 'w', 0.02, 2, 0.01)));
    if (L.type !== 'text') p.appendChild(row('Înălțime', mkRange(L, 'h', 0.02, 2, 0.01)));
    p.appendChild(row('Rotație', mkRange(L, 'rotation', 0, 360, 1)));
  }
  p.appendChild(row('Opacitate', mkRange(L, 'opacity', 0, 1, 0.01)));
  p.appendChild(row('Blur', mkRange(L, 'blur', 0, 40, 1)));

  // Shadow
  grpH(p, 'UMBRĂ');
  p.appendChild(row('Activă', mkCheck(L.shadow, 'enabled')));
  p.appendChild(row('Culoare', mkColor(L.shadow, 'color')));
  p.appendChild(row('Blur', mkRange(L.shadow, 'blur', 0, 80, 1)));
  p.appendChild(row('Offset X', mkRange(L.shadow, 'x', -60, 60, 1)));
  p.appendChild(row('Offset Y', mkRange(L.shadow, 'y', -60, 60, 1)));

  // Animations
  grpH(p, 'ANIMAȚIE (cât e afișat)');
  animToggle(p, L, 'pulse',  'Pulsare (opac.)', [['speed',0.1,5,0.1],['min',0,1,0.01],['max',0,1,0.01]]);
  animToggle(p, L, 'scale',  'Pulsare (mărime)', [['speed',0.1,5,0.1],['min',0.5,1,0.01],['max',1,1.5,0.01]]);
  animToggle(p, L, 'float',  'Plutire',          [['speed',0.1,5,0.1],['amp',0,0.2,0.005]]);
  animToggle(p, L, 'spin',   'Rotire continuă',  [['speed',0.05,2,0.05]]);
  animToggle(p, L, 'glow',   'Glow pulsant',     [['speed',0.1,5,0.1],['min',0,40,1],['max',0,80,1]]);
  animToggle(p, L, 'chaos',  'Haotic (wow)',     [['speed',0.1,4,0.1],['amp',0,0.2,0.005]]);

  // Entrance / Exit
  const TR = ['none','fade','slide_left','slide_right','slide_up','slide_down',
              'rise','drop','zoom_in','zoom_out','blur','pop',
              'zoom_blur','slide_blur_left','slide_blur_right','rotate_in',
              'swing','bounce','flip_x','glitch'];
  const ent = (L.entrance = L.entrance || { type:'fade', duration:700, delay:0 });
  const ex  = (L.exit     = L.exit     || { type:'fade', duration:500, delay:0 });
  grpH(p, 'INTRARE');
  p.appendChild(row('Efect',    mkSelect(ent, 'type', TR, null, _TR_GLYPH)));
  p.appendChild(row('Durată',   mkRange(ent, 'duration', 100, 4000, 50)));
  p.appendChild(row('Întârziere', mkRange(ent, 'delay', 0, 4000, 50)));
  const inBtn = document.createElement('button'); inBtn.className = 'btn';
  inBtn.textContent = '▶ Preview intrare'; inBtn.onclick = () => previewPhase('intro');
  p.appendChild(row('', inBtn));
  grpH(p, 'IEȘIRE');
  p.appendChild(row('Efect',    mkSelect(ex, 'type', TR, null, _TR_GLYPH)));
  p.appendChild(row('Durată',   mkRange(ex, 'duration', 100, 4000, 50)));
  p.appendChild(row('Întârziere', mkRange(ex, 'delay', 0, 4000, 50)));
  const outBtn = document.createElement('button'); outBtn.className = 'btn';
  outBtn.textContent = '▶ Preview ieșire'; outBtn.onclick = () => previewPhase('outro');
  p.appendChild(row('', outBtn));
}

function buildClockProps(p, L) {
  grpH(p, 'CEAS / CRONOMETRU');
  const mode = L.clockMode || 'clock';
  const modeSel = document.createElement('select');
  [['clock', 'Ceas (oră curentă)'], ['date', 'Dată'],
   ['stopwatch', 'Cronometru ↑'], ['countdown', 'Num. inversă ↓']].forEach(([v, lbl]) => {
    const o = document.createElement('option'); o.value = v; o.textContent = lbl;
    if (mode === v) o.selected = true;
    modeSel.appendChild(o);
  });
  modeSel.onchange = () => { L.clockMode = modeSel.value; rebuildProps(); };
  p.appendChild(row('Mod', modeSel));

  if (mode === 'clock') {
    p.appendChild(row('Format 24h', mkCheck(L, 'format24')));
    p.appendChild(row('Secunde', mkCheck(L, 'showSeconds')));
  } else if (mode === 'countdown') {
    p.appendChild(row('Durată (sec)', mkRange(L, 'duration', 5, 3600, 5)));
    // End-of-countdown sound
    const sc = document.createElement('div'); sc.className = 'ctl';
    const nm = document.createElement('span');
    nm.style.cssText = 'font-size:10px;color:#aaa;margin-right:6px;';
    nm.textContent = L.endSound ? String(L.endSound).split(/[\\/]/).pop() : '(fără sunet)';
    const pick = document.createElement('button'); pick.textContent = '🔊';
    pick.title = 'Alege un sunet redat la finalul numărătorii';
    pick.onclick = () => {
      const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'audio/*';
      inp.onchange = () => { const f = inp.files[0]; if (f) { L.endSound = f.path || ''; rebuildProps(); } };
      inp.click();
    };
    const clr = document.createElement('button'); clr.textContent = '✕';
    clr.title = 'Fără sunet';
    clr.onclick = () => { L.endSound = ''; rebuildProps(); };
    sc.appendChild(nm); sc.appendChild(pick); sc.appendChild(clr);
    p.appendChild(row('Sunet la final', sc));
  }

  p.appendChild(row('Font', mkFontPicker(L, 'font')));
  p.appendChild(row('Mărime', mkRange(L, 'size', 20, 500, 1)));
  const styleRow = document.createElement('div'); styleRow.className = 'row';
  styleRow.innerHTML = '<label>Stil</label>';
  const c = document.createElement('div'); c.className = 'ctl';
  c.appendChild(labeledCheck(L, 'bold', 'B'));
  c.appendChild(labeledCheck(L, 'italic', 'I'));
  c.appendChild(labeledCheck(L, 'uppercase', 'AA'));
  styleRow.appendChild(c); p.appendChild(styleRow);
  p.appendChild(row('Aliniere', mkSelect(L, 'align', ['left', 'center', 'right'])));
  p.appendChild(row('Spațiere', mkRange(L, 'letterSpacing', -5, 40, 1)));

  grpH(p, 'CULOARE');
  p.appendChild(row('Tip', mkSelect(L, 'colorType', ['solid', 'gradient', 'animated'])));
  p.appendChild(row('Culoare', mkColor(L, 'color')));
  p.appendChild(row('Grad. de la', mkColor(L, 'gradFrom')));
  p.appendChild(row('Grad. la', mkColor(L, 'gradTo')));

  grpH(p, 'PREFIX / SUFIX');
  p.appendChild(row('Prefix', mkText(L, 'prefix')));
  p.appendChild(row('Sufix', mkText(L, 'suffix')));
}

function buildLyricsProps(p, L) {
  grpH(p, 'VERSURI (cascadă)');
  p.appendChild(row('Font', mkFontPicker(L, 'font')));
  p.appendChild(row('Mărime', mkRange(L, 'size', 20, 200, 1)));
  p.appendChild(row('Bold', mkCheck(L, 'bold')));
  p.appendChild(row('Majuscule', mkCheck(L, 'uppercase')));
  p.appendChild(row('Aliniere', mkSelect(L, 'align', ['left','center','right'])));
  p.appendChild(row('Linii vizibile', mkRange(L, 'visibleLines', 3, 9, 2)));
  p.appendChild(row('Spațiere', mkRange(L, 'lineGap', 1.0, 3.0, 0.05)));
  p.appendChild(row('Viteză scroll', mkRange(L, 'scrollSpeed', 2, 20, 1)));
  grpH(p, 'LINIA CURENTĂ');
  p.appendChild(row('Culoare', mkColor(L, 'hlColor')));
  p.appendChild(row('Scalare', mkRange(L, 'hlScale', 1.0, 1.8, 0.02)));
  p.appendChild(row('Glow', mkCheck(L, 'hlGlow')));
  grpH(p, 'LINII SECUNDARE');
  p.appendChild(row('Culoare', mkColor(L, 'dimColor')));
  p.appendChild(row('Opacitate', mkRange(L, 'dimOpacity', 0.05, 1, 0.05)));
}

function buildGradientProps(p, L) {
  grpH(p, 'GRADIENT');
  // Preset picker — applies colours + animation in one click
  const presets = (window.BgEngine && BgEngine.GRADIENT_PRESETS) || {};
  const presetSel = document.createElement('select');
  const ph = document.createElement('option');
  ph.value = ''; ph.textContent = '— Presetare —'; presetSel.appendChild(ph);
  Object.keys(presets).forEach(n => {
    const o = document.createElement('option'); o.value = n; o.textContent = n;
    presetSel.appendChild(o);
  });
  presetSel.value = L.preset || '';
  presetSel.onchange = () => {
    if (presetSel.value && window.BgEngine) {
      BgEngine.applyGradientPreset(L, presetSel.value);
      rebuildProps();
    }
  };
  p.appendChild(row('Presetare', presetSel));

  p.appendChild(row('Tip', mkSelect(L, 'gradientType', ['linear','radial','conic'])));
  p.appendChild(row('Unghi', mkRange(L, 'angle', 0, 360, 1)));
  // stops
  const wrap = document.createElement('div'); wrap.className = 'stops';
  (L.stops || []).forEach((s, i) => {
    const r = document.createElement('div'); r.className = 'stop';
    const col = document.createElement('input'); col.type = 'color'; col.value = s.color;
    col.oninput = () => { s.color = col.value; };
    const rng = document.createElement('input'); rng.type = 'range';
    rng.min = 0; rng.max = 1; rng.step = 0.01; rng.value = s.pos;
    rng.oninput = () => { s.pos = parseFloat(rng.value); };
    const del = document.createElement('button'); del.className = 'mini'; del.textContent = '🗑';
    del.onclick = () => { L.stops.splice(i, 1); rebuildProps(); };
    r.appendChild(col); r.appendChild(rng); r.appendChild(del);
    wrap.appendChild(r);
  });
  const addStop = document.createElement('button');
  addStop.className = 'btn'; addStop.textContent = '+ Stop culoare';
  addStop.style.marginTop = '4px';
  addStop.onclick = () => { L.stops.push({ pos: 1, color: '#ffffff' }); rebuildProps(); };
  wrap.appendChild(addStop);
  p.appendChild(wrap);

  grpH(p, 'ANIMAȚIE GRADIENT');
  const modes = (window.BgEngine && BgEngine.GRADIENT_MODES) ||
    ['none','rotate','shift','cycle'];
  p.appendChild(row('Mod', mkSelect(L.animate, 'mode', modes)));
  p.appendChild(row('Viteză', mkRange(L.animate, 'speed', 0.05, 3, 0.05)));
}

function buildParticleProps(p, L) {
  grpH(p, 'PARTICULE');
  p.appendChild(row('Tip', mkSelect(L, 'preset', ['sparks','snow','fog','bokeh','embers'])));
  p.appendChild(row('Număr', mkRange(L, 'count', 10, 500, 5, rebuildLayers)));
  p.appendChild(row('Culoare', mkColor(L, 'color')));
  p.appendChild(row('Culoare 2', mkColor(L, 'color2')));
  p.appendChild(row('Viteză', mkRange(L, 'speed', 0.1, 4, 0.1)));
  p.appendChild(row('Mărime', mkRange(L, 'size', 0.2, 4, 0.1)));
}

function buildShapeProps(p, L) {
  grpH(p, 'FORMĂ');
  p.appendChild(row('Tip', mkShapePicker(L)));
  p.appendChild(row('Umplere', mkSelect(L, 'fillType', ['solid','gradient','none'])));
  p.appendChild(row('Culoare', mkColor(L, 'color')));
  p.appendChild(row('Grad. de la', mkColor(L, 'gradFrom')));
  p.appendChild(row('Grad. la', mkColor(L, 'gradTo')));
  p.appendChild(row('Grad. unghi', mkRange(L, 'gradAngle', 0, 360, 1)));
  p.appendChild(row('Colț rotund', mkRange(L, 'radius', 0, 300, 1)));
  p.appendChild(row('Contur', mkColor(L, 'strokeColor')));
  p.appendChild(row('Gros. contur', mkRange(L, 'strokeWidth', 0, 40, 1)));
}

function buildTextProps(p, L) {
  grpH(p, 'TEXT');
  p.appendChild(row('Conținut', mkArea(L, 'text')));
  p.appendChild(row('Font', mkFontPicker(L, 'font')));
  p.appendChild(row('Mărime', mkRange(L, 'size', 12, 400, 1)));
  const styleRow = document.createElement('div'); styleRow.className = 'row';
  styleRow.innerHTML = '<label>Stil</label>';
  const c = document.createElement('div'); c.className = 'ctl';
  c.appendChild(labeledCheck(L, 'bold', 'B'));
  c.appendChild(labeledCheck(L, 'italic', 'I'));
  c.appendChild(labeledCheck(L, 'uppercase', 'AA'));
  styleRow.appendChild(c); p.appendChild(styleRow);
  p.appendChild(row('Aliniere', mkSelect(L, 'align', ['left','center','right'])));
  p.appendChild(row('Înălț. linie', mkRange(L, 'lineHeight', 0.8, 2.5, 0.05)));
  p.appendChild(row('Spațiere', mkRange(L, 'letterSpacing', -5, 40, 1)));

  grpH(p, 'CULOARE TEXT');
  p.appendChild(row('Tip', mkSelect(L, 'colorType', ['solid','gradient','animated'])));
  p.appendChild(row('Culoare', mkColor(L, 'color')));
  p.appendChild(row('Grad. de la', mkColor(L, 'gradFrom')));
  p.appendChild(row('Grad. la', mkColor(L, 'gradTo')));

  grpH(p, 'ECOU (text mare în spate)');
  p.appendChild(row('Activ', mkCheck(L.echo, 'enabled')));
  p.appendChild(row('Scară', mkRange(L.echo, 'scale', 1.2, 5, 0.1)));
  p.appendChild(row('Opacitate', mkRange(L.echo, 'opacity', 0.02, 0.6, 0.01)));
  p.appendChild(row('Blur', mkRange(L.echo, 'blur', 0, 12, 1)));
}

function buildMediaProps(p, L) {
  grpH(p, L.type === 'video' ? 'VIDEO' : 'IMAGINE');
  const r = document.createElement('div'); r.className = 'row';
  r.innerHTML = '<label>Fișier</label>';
  const c = document.createElement('div'); c.className = 'ctl';
  const b = document.createElement('button'); b.className = 'btn';
  b.textContent = '📁 Alege…'; b.onclick = () => pickMedia(L);
  const nm = document.createElement('span'); nm.style.cssText = 'font-size:10px;color:#888;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
  nm.textContent = L.src ? L.src.split(/[\\/]/).pop() : '(niciun fișier)';
  c.appendChild(b); c.appendChild(nm); r.appendChild(c); p.appendChild(r);
  p.appendChild(row('Încadrare', mkSelect(L, 'fit', ['cover','contain','stretch'])));
  if (L.type === 'video') { p.appendChild(row('Loop', mkCheck(L, 'loop'))); }
}

// Load + register an image/video layer's media element (once, cached on the
// layer under a `_`-prefixed key so it is never serialised). Mirrors display.js
// so backgrounds pulled in via the picker — or any saved doc — show their media.
function ensureLayerMedia(L) {
  if (!L || (L.type !== 'image' && L.type !== 'video') || !L.src) return;
  if (L._mediaEl) { BgEngine.registerMedia(L.id, L._mediaEl, L.type); return; }
  const isVideo = L.type === 'video';
  const el = isVideo ? document.createElement('video') : new Image();
  if (isVideo) { el.loop = (L.loop !== false); el.muted = true; el.autoplay = true; el.playsInline = true; }
  el.onloadeddata = el.onload = () => BgEngine.registerMedia(L.id, el, L.type);
  el.src = /^(file|https?|data|blob):/i.test(L.src)
    ? L.src : ('file:///' + String(L.src).replace(/\\/g, '/'));
  if (isVideo) el.play().catch(() => {});
  L._mediaEl = el;
  BgEngine.registerMedia(L.id, el, L.type);
}

function pickMedia(L) {
  const inp = document.createElement('input');
  inp.type = 'file';
  inp.accept = L.type === 'video' ? 'video/*' : 'image/*';
  inp.onchange = () => {
    const f = inp.files[0]; if (!f) return;
    const path = f.path || URL.createObjectURL(f);  // Electron gives .path
    L.src = f.path || path;
    const el = L.type === 'video' ? document.createElement('video') : new Image();
    if (L.type === 'video') { el.loop = true; el.muted = true; el.autoplay = true; el.playsInline = true; }
    el.onloadeddata = el.onload = () => BgEngine.registerMedia(L.id, el, L.type);
    el.src = (f.path ? 'file:///' + f.path.replace(/\\/g, '/') : path);
    if (L.type === 'video') el.play().catch(() => {});
    BgEngine.registerMedia(L.id, el, L.type);
    rebuildProps();
  };
  inp.click();
}

// ── Control builders ──────────────────────────────────────────────────────────

function grpH(parent, txt) { const d = document.createElement('div'); d.className = 'grp-h'; d.textContent = txt; parent.appendChild(d); }

function row(label, ctl) {
  const r = document.createElement('div'); r.className = 'row';
  const l = document.createElement('label'); l.textContent = label;
  const c = document.createElement('div'); c.className = 'ctl'; c.appendChild(ctl);
  r.appendChild(l); r.appendChild(c); return r;
}

function mkText(obj, key, after) {
  const i = document.createElement('input'); i.type = 'text'; i.value = obj[key] != null ? obj[key] : '';
  i.oninput = () => { obj[key] = i.value; if (after) after(); };
  return i;
}
function mkArea(obj, key) {
  const a = document.createElement('textarea'); a.value = obj[key] != null ? obj[key] : '';
  a.oninput = () => { obj[key] = a.value; };
  return a;
}
function mkColor(obj, key) {
  const i = document.createElement('input'); i.type = 'color'; i.value = obj[key] || '#000000';
  i.oninput = () => { obj[key] = i.value; };
  return i;
}
function mkCheck(obj, key) {
  const i = document.createElement('input'); i.type = 'checkbox'; i.checked = !!obj[key];
  i.onchange = () => { obj[key] = i.checked; };
  return i;
}
function labeledCheck(obj, key, label) {
  const w = document.createElement('label');
  w.style.cssText = 'display:flex;align-items:center;gap:3px;color:#ccc;font-size:11px;width:auto';
  const i = document.createElement('input'); i.type = 'checkbox'; i.checked = !!obj[key];
  i.onchange = () => { obj[key] = i.checked; };
  w.appendChild(i); w.appendChild(document.createTextNode(label));
  return w;
}
const _TR_GLYPH = {
  none: '∅', fade: '▒', slide_left: '←', slide_right: '→', slide_up: '↑', slide_down: '↓',
  rise: '⤒', drop: '⤓', zoom_in: '⊕', zoom_out: '⊖', blur: '░', pop: '✸',
  zoom_blur: '✷', slide_blur_left: '⇜', slide_blur_right: '⇝', rotate_in: '↻',
  swing: '⇄', bounce: '⤴', flip_x: '⇋', glitch: '▚',
};
function mkSelect(obj, key, opts, after, glyphs) {
  const s = document.createElement('select');
  opts.forEach(o => {
    const op = document.createElement('option');
    op.value = o;   // keep the raw value; glyph is display-only
    op.textContent = (glyphs && glyphs[o] ? glyphs[o] + '  ' : '') + o;
    s.appendChild(op);
  });
  s.value = obj[key] != null ? obj[key] : opts[0];
  s.onchange = () => { obj[key] = s.value; if (after) after(); rebuildProps(); };
  return s;
}
function mkFontPicker(obj, key) {
  // Each <option> rendered in its own font (Chromium honours option font-family).
  const fonts = (window.CantioFonts && CantioFonts.FONTS) || ['Montserrat', 'Arial'];
  const s = document.createElement('select');
  fonts.forEach(f => {
    const o = document.createElement('option');
    o.value = f; o.textContent = f;
    o.style.fontFamily = `"${f}", sans-serif`;
    s.appendChild(o);
  });
  s.value = obj[key] || fonts[0];
  s.style.fontFamily = `"${s.value}", sans-serif`;
  s.style.fontSize = '13px';
  s.onchange = () => {
    obj[key] = s.value;
    s.style.fontFamily = `"${s.value}", sans-serif`;
  };
  return s;
}

function mkShapePicker(obj) {
  const wrap = document.createElement('div');
  wrap.style.cssText = 'display:grid;grid-template-columns:repeat(6,1fr);gap:4px;flex:1';
  const shapes = (window.BgEngine && BgEngine.SHAPE_LIST) || ['rect', 'circle'];
  const cells = {};
  shapes.forEach(sh => {
    const c = document.createElement('canvas');
    c.width = 36; c.height = 28; c.title = sh;
    c.style.cssText = 'border-radius:4px;cursor:pointer;background:#1c1c1c;border:1px solid '
      + (obj.shape === sh ? '#5294e2' : '#262626');
    try {
      if (window.BgEngine && BgEngine.drawShapeIcon)
        BgEngine.drawShapeIcon(c.getContext('2d'), sh, 36, 28, '#5294e2');
    } catch (e) {}
    c.onclick = () => {
      obj.shape = sh;
      for (const k in cells) cells[k].style.borderColor = (k === sh) ? '#5294e2' : '#262626';
    };
    cells[sh] = c;
    wrap.appendChild(c);
  });
  return wrap;
}

function mkRange(obj, key, min, max, step, after) {
  const wrap = document.createElement('div'); wrap.style.cssText = 'display:flex;align-items:center;gap:6px;flex:1';
  const i = document.createElement('input'); i.type = 'range';
  i.min = min; i.max = max; i.step = step;
  i.value = (obj[key] != null ? obj[key] : min);
  const v = document.createElement('span'); v.className = 'val'; v.textContent = fmtVal(i.value);
  i.oninput = () => { obj[key] = parseFloat(i.value); v.textContent = fmtVal(i.value); if (after) after(); };
  wrap.appendChild(i); wrap.appendChild(v); return wrap;
}
function fmtVal(v) { v = parseFloat(v); return (v % 1 === 0) ? String(v) : v.toFixed(2); }
function mkNum(obj, key) {
  const i = document.createElement('input'); i.type = 'number'; i.value = obj[key];
  i.oninput = () => { obj[key] = parseFloat(i.value) || 0; };
  return i;
}

function animToggle(parent, L, name, label, params) {
  const a = (L.anim = L.anim || {});
  const o = (a[name] = a[name] || { enabled: false, speed: 1 });
  parent.appendChild(row(label, mkCheck(o, 'enabled')));
  params.forEach(([k, mn, mx, st]) => {
    if (o[k] == null) o[k] = mn;
    parent.appendChild(row('• ' + k, mkRange(o, k, mn, mx, st)));
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));
}

// ── Wire top bar ──────────────────────────────────────────────────────────────

$('saveBtn').onclick = saveBg;
$('closeBtn').onclick = () => { if (_ipc) { try { _ipc.send('bg_editor_close'); } catch (e) {} } window.close(); };
$('playBtn').onclick = () => {
  if (state.playing) { state.tHold = performance.now() - state.t0; state.playing = false; $('playBtn').textContent = '▶'; }
  else { state.t0 = performance.now() - state.tHold; state.playing = true; $('playBtn').textContent = '⏸'; }
};
const _rulerBtn = $('rulerBtn');
if (_rulerBtn) {
  _rulerBtn.classList.toggle('active', state.rulers);
  _rulerBtn.onclick = () => { state.rulers = !state.rulers; _rulerBtn.classList.toggle('active', state.rulers); };
}
const _bgPickerBtn = $('bgPickerBtn');
if (_bgPickerBtn) _bgPickerBtn.onclick = openBgPicker;
$('bgName').oninput = () => {
  if (state.multi) state.wrapper.name = $('bgName').value;
  else state.bg.name = $('bgName').value;
};
const _addSlideBtn = $('addSlideBtn');
if (_addSlideBtn) _addSlideBtn.onclick = addSlide;

document.querySelectorAll('.add-bar .btn[data-add]').forEach(b =>
  b.onclick = () => addLayer(b.getAttribute('data-add')));

// Apply a new format. In multi-slide (song) mode the format is shared by all
// slides, so update the wrapper and every slide.
function setFormat(w, h) {
  if (state.multi) {
    state.wrapper.format = { w, h };
    state.wrapper.slides.forEach(s => { s.format = { w, h }; });
    state.bg.format = state.wrapper.format;
  } else {
    state.bg.format = { w, h };
  }
  applyFormat();
  rebuildSlides();
}
$('formatSel').onchange = () => {
  const val = $('formatSel').value;
  if (val === 'custom') {
    $('customW').style.display = ''; $('customH').style.display = '';
  } else {
    const [w, h] = val.split('x').map(Number);
    setFormat(w, h);
  }
};
function applyCustom() {
  const w = parseInt($('customW').value) || 1920, h = parseInt($('customH').value) || 1080;
  setFormat(w, h);
}
$('customW').onchange = applyCustom;
$('customH').onchange = applyCustom;

window.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); saveBg(); }
});

// ── Boot ──────────────────────────────────────────────────────────────────────

loadBg();
if (state.multi) {
  $('body').classList.add('multi');
  $('slidesRail').style.display = 'flex';
  document.querySelector('.title').textContent = '🎬 Editor Slide-uri';
  $('bgName').value = state.wrapper.name || '';
  rebuildSlides();
} else {
  $('bgName').value = state.bg.name || '';
}
applyFormat();
rebuildLayers();
if (state.bg.layers[0]) selectLayer(state.bg.layers[0].id);
rebuildProps();
requestAnimationFrame(renderLoop);
