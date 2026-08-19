// Cantio — Electron Theme Editor
// Full live-render theme editor: edit a theme's text/background/layout, type sample
// text, and see it rendered by the same engine the live output uses. Replaces the
// old PyQt theme editor. Unedited theme keys are PRESERVED so nothing is lost.

'use strict';
let _ipc = null;
try { _ipc = (typeof require !== 'undefined') ? require('electron').ipcRenderer : null; } catch (e) {}
const _fs   = (typeof require !== 'undefined') ? require('fs')   : null;

const DEFAULT_SAMPLE = 'Slăvit să fie Domnul\nÎn veci îndurarea Lui';

// ── State ──────────────────────────────────────────────────────────────────────
let filePath = '';
let themeName = '';
let theme = {};                 // the full theme dict (preserved on save)
let sample = DEFAULT_SAMPLE;
let curTab = 'text';

const canvas = document.getElementById('preview');
const ctx = canvas.getContext('2d');

// ── Query param (file with {name, theme}) ────────────────────────────────────────
(function loadFromQuery() {
  try {
    const q = new URLSearchParams(location.search);
    filePath = q.get('file') || '';
    if (filePath && _fs) {
      const raw = JSON.parse(_fs.readFileSync(filePath, 'utf-8'));
      themeName = raw.name || 'Temă';
      theme = raw.theme || {};
    }
  } catch (e) { console.error('theme load', e); }
  if (!theme.text) theme.text = {};
  if (!theme.background) theme.background = { type: 'color', color: '#0d1030' };
  if (!theme.layout) theme.layout = {};
  document.getElementById('themeName').textContent = themeName;
})();

// ── Helpers to read theme fields with defaults ───────────────────────────────────
const T = () => theme.text;
const B = () => theme.background;
const L = () => theme.layout;
function tv(o, k, d) { const v = o[k]; return (v === undefined || v === null || v === '') ? d : v; }
function tb(o, k, d) { const v = o[k]; if (v === undefined) return d; return v === true || v === 'true'; }
function tn(o, k, d) { const v = parseFloat(o[k]); return isNaN(v) ? d : v; }

// ── Live render ──────────────────────────────────────────────────────────────────
function render() {
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  drawBg(W, H);
  drawText(W, H);
}

function drawBg(W, H) {
  const b = B();
  const type = tv(b, 'type', 'color');
  if (type === 'gradient' || type === 'animated_gradient') {
    const cols = type === 'animated_gradient'
      ? (b.anim_colors || ['#1a237e', '#6a1b9a', '#0d47a1'])
      : [tv(b, 'grad_from', tv(b, 'color', '#101030')), tv(b, 'grad_to', '#000000')];
    const g = ctx.createLinearGradient(0, 0, W, H);
    cols.forEach((c, i) => g.addColorStop(i / Math.max(1, cols.length - 1), c));
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  } else if (type === 'image' || type === 'video' || type === 'camera' ||
             type === 'camera_gradient' || type === 'fundal') {
    // Media backgrounds render live on the projector; show a marker here.
    ctx.fillStyle = tv(b, 'color', '#101018'); ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = 'rgba(255,255,255,0.14)';
    ctx.font = '13px Segoe UI'; ctx.textAlign = 'center';
    ctx.fillText('◧ fundal ' + type + ' (vizibil live)', W / 2, H - 16);
  } else if (type === 'transparent') {
    // checkerboard
    const s = 20;
    for (let y = 0; y < H; y += s) for (let x = 0; x < W; x += s) {
      ctx.fillStyle = ((x / s + y / s) % 2 === 0) ? '#2a2a34' : '#1c1c24';
      ctx.fillRect(x, y, s, s);
    }
  } else {
    ctx.fillStyle = tv(b, 'color', '#0d1030'); ctx.fillRect(0, 0, W, H);
  }
}

function drawText(W, H) {
  const t = T();
  let text = sample || '';
  if (tb(t, 'uppercase', false)) text = text.toUpperCase();
  const lines = text.split('\n');
  const scale = W / 1920;
  const size = Math.max(8, tn(t, 'font_size', 72) * scale);
  const family = tv(t, 'font_family', 'Montserrat');
  const bold = tb(t, 'font_bold', true) ? '700 ' : '400 ';
  const italic = tb(t, 'font_italic', false) ? 'italic ' : '';
  ctx.font = italic + bold + size + 'px "' + family + '"';
  ctx.textBaseline = 'middle';
  const align = tv(t, 'text_align', 'center');
  ctx.textAlign = align === 'left' ? 'left' : align === 'right' ? 'right' : 'center';
  const x = align === 'left' ? W * 0.06 : align === 'right' ? W * 0.94 : W / 2;

  const lineH = size * tn(t, 'line_spacing', 1.15);
  const valign = tv(L(), 'valign', 'center');
  let y0;
  const totalH = lines.length * lineH;
  if (valign === 'top')    y0 = H * 0.10 + lineH / 2;
  else if (valign === 'bottom') y0 = H * 0.90 - totalH + lineH / 2;
  else y0 = H / 2 - totalH / 2 + lineH / 2;

  const outlineW = tn(t, 'outline_width', 0) * scale;
  const outlineC = tv(t, 'outline_color', '#000000');
  const shadow = tb(t, 'text_shadow', false);
  const colorType = tv(t, 'color_type', 'solid');

  lines.forEach((ln, i) => {
    const y = y0 + i * lineH;
    if (shadow) {
      ctx.save();
      ctx.shadowColor = tv(t, 'shadow_color', 'rgba(0,0,0,0.8)');
      ctx.shadowBlur = 6 * scale; ctx.shadowOffsetX = 2 * scale; ctx.shadowOffsetY = 2 * scale;
      ctx.fillStyle = tv(t, 'text_color', '#ffffff'); ctx.fillText(ln, x, y);
      ctx.restore();
    }
    if (outlineW > 0) {
      ctx.lineWidth = outlineW * 2; ctx.strokeStyle = outlineC;
      ctx.lineJoin = 'round'; ctx.strokeText(ln, x, y);
    }
    if (colorType === 'gradient') {
      const g = ctx.createLinearGradient(0, y - size / 2, 0, y + size / 2);
      g.addColorStop(0, tv(t, 'grad_from', '#ffffff'));
      g.addColorStop(1, tv(t, 'grad_to', '#9ec5ff'));
      ctx.fillStyle = g;
    } else {
      ctx.fillStyle = tv(t, 'text_color', '#ffffff');
    }
    ctx.fillText(ln, x, y);
  });
}

// ── Control builders ─────────────────────────────────────────────────────────────
function el(tag, cls, txt) { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
function row(label, ctl) {
  const r = el('div', 'row'); r.appendChild(el('label', null, label));
  const c = el('div', 'ctl'); c.appendChild(ctl); r.appendChild(c); return r;
}
function grpH(txt) { return el('div', 'grp-h', txt); }

function mkColor(obj, key, def) {
  const i = document.createElement('input'); i.type = 'color';
  i.value = toHex(tv(obj, key, def));
  i.oninput = () => { obj[key] = i.value; render(); };
  return i;
}
function toHex(c) { if (!c) return '#000000'; if (c[0] === '#' && c.length >= 7) return c.slice(0, 7); return c; }
function mkRange(obj, key, min, max, step, def, unit) {
  const wrap = el('div', 'ctl');
  const r = document.createElement('input'); r.type = 'range';
  r.min = min; r.max = max; r.step = step; r.value = tv(obj, key, def);
  const v = el('span', 'val', r.value + (unit || ''));
  r.oninput = () => { obj[key] = String(r.value); v.textContent = r.value + (unit || ''); render(); };
  wrap.appendChild(r); wrap.appendChild(v); return wrap;
}
function mkSelect(obj, key, opts, def) {
  const s = document.createElement('select');
  opts.forEach(o => { const op = document.createElement('option'); op.value = o; op.textContent = o; s.appendChild(op); });
  s.value = tv(obj, key, def);
  s.onchange = () => { obj[key] = s.value; buildPanel(); render(); };
  return s;
}
function mkCheck(obj, key, label, def) {
  const l = el('label', 'chk'); const c = document.createElement('input'); c.type = 'checkbox';
  c.checked = tb(obj, key, def); c.onchange = () => { obj[key] = c.checked ? 'true' : 'false'; buildPanel(); render(); };
  l.appendChild(c); l.appendChild(document.createTextNode(label)); return l;
}
function mkText(obj, key, def) {
  const i = document.createElement('input'); i.type = 'text'; i.value = tv(obj, key, def);
  i.oninput = () => { obj[key] = i.value; render(); }; return i;
}

// ── Panels ───────────────────────────────────────────────────────────────────────
function buildPanel() {
  const p = document.getElementById('panel'); p.innerHTML = '';
  if (curTab === 'text') buildTextPanel(p);
  else if (curTab === 'bg') buildBgPanel(p);
  else buildLayoutPanel(p);
}

function buildTextPanel(p) {
  const t = T();
  p.appendChild(grpH('Font'));
  p.appendChild(row('Font', mkText(t, 'font_family', 'Montserrat')));
  p.appendChild(row('Mărime', mkRange(t, 'font_size', 12, 400, 1, 72, '')));
  const style = el('div', 'ctl');
  style.appendChild(mkCheck(t, 'font_bold', 'B', true));
  style.appendChild(mkCheck(t, 'font_italic', 'I', false));
  style.appendChild(mkCheck(t, 'uppercase', 'AA', false));
  p.appendChild(row('Stil', style));
  p.appendChild(row('Aliniere', mkSelect(t, 'text_align', ['left', 'center', 'right'], 'center')));
  p.appendChild(row('Spațiere', mkRange(t, 'line_spacing', 0.8, 2.5, 0.05, 1.15, '')));

  p.appendChild(grpH('Culoare'));
  p.appendChild(row('Tip', mkSelect(t, 'color_type', ['solid', 'gradient'], 'solid')));
  if (tv(t, 'color_type', 'solid') === 'gradient') {
    p.appendChild(row('De la', mkColor(t, 'grad_from', '#ffffff')));
    p.appendChild(row('Până la', mkColor(t, 'grad_to', '#9ec5ff')));
  } else {
    p.appendChild(row('Culoare', mkColor(t, 'text_color', '#ffffff')));
  }

  p.appendChild(grpH('Contur & Umbră'));
  p.appendChild(row('Gros. contur', mkRange(t, 'outline_width', 0, 20, 1, 0, '')));
  p.appendChild(row('Culoare contur', mkColor(t, 'outline_color', '#000000')));
  p.appendChild(row('Umbră', mkCheck(t, 'text_shadow', 'Activă', false)));
}

function buildBgPanel(p) {
  const b = B();
  p.appendChild(grpH('Fundal'));
  p.appendChild(row('Tip', mkSelect(b, 'type',
    ['color', 'gradient', 'animated_gradient', 'image', 'video', 'camera', 'fundal', 'transparent'], 'color')));
  const type = tv(b, 'type', 'color');
  if (type === 'color') {
    p.appendChild(row('Culoare', mkColor(b, 'color', '#0d1030')));
  } else if (type === 'gradient') {
    p.appendChild(row('De la', mkColor(b, 'grad_from', '#101030')));
    p.appendChild(row('Până la', mkColor(b, 'grad_to', '#000000')));
  } else if (type === 'animated_gradient') {
    const info = el('div', null, 'Gradient animat — culorile se editează live pe proiector.');
    info.style.cssText = 'color:#6c7086;font-size:10px;'; p.appendChild(info);
  } else {
    const info = el('div', null, 'Fundal media (imagine/video/cameră/fundal) — se alege și se vede live.');
    info.style.cssText = 'color:#6c7086;font-size:10px;line-height:1.5;'; p.appendChild(info);
    if (type === 'camera' || type === 'camera_gradient') {
      const c2 = el('div', null, '📷 Camera se alege din Media → Feeds.');
      c2.style.cssText = 'color:#6c7086;font-size:10px;margin-top:4px;'; p.appendChild(c2);
    }
  }
}

function buildLayoutPanel(p) {
  const l = L();
  p.appendChild(grpH('Poziționare'));
  p.appendChild(row('Aliniere V', mkSelect(l, 'valign', ['top', 'center', 'bottom'], 'center')));
  p.appendChild(row('Margine', mkRange(l, 'margin', 0, 300, 5, 60, ' px')));
}

// ── Tabs + sample text + save ────────────────────────────────────────────────────
document.querySelectorAll('.tabs button').forEach(b => {
  b.onclick = () => {
    document.querySelectorAll('.tabs button').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); curTab = b.getAttribute('data-tab'); buildPanel();
  };
});
const sampleBox = document.getElementById('sampleText');
sampleBox.value = sample;
sampleBox.oninput = () => { sample = sampleBox.value; render(); };

document.getElementById('btnSave').onclick = () => {
  theme.text = T(); theme.background = B(); theme.layout = L();
  try {
    if (filePath && _fs) _fs.writeFileSync(filePath, JSON.stringify({ name: themeName, theme }, null, 2), 'utf-8');
  } catch (e) { console.error('save', e); }
  if (_ipc) { try { _ipc.send('theme_saved', themeName); } catch (e) {} }
  const btn = document.getElementById('btnSave');
  btn.textContent = '✓ Salvat'; setTimeout(() => { btn.textContent = '💾 Salvează'; }, 1200);
};
document.getElementById('btnClose').onclick = () => { window.close(); };

// ── Boot ─────────────────────────────────────────────────────────────────────────
buildPanel();
render();
setInterval(render, 1000);   // keep animated bg/clock-ish previews fresh
