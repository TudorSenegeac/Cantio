const Utils = {
  $: (sel, ctx) => (ctx || document).querySelector(sel),
  $$: (sel, ctx) => Array.from((ctx || document).querySelectorAll(sel)),
  escapeHtml: (s) => {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  },
  debounce: (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; },
  clamp: (v, min, max) => Math.max(min, Math.min(max, v)),
  randomId: () => Math.random().toString(36).slice(2, 9),

  toast: (message, type = 'info', duration = 3000) => {
    const container = Utils.$('#toast-container');
    if (!container) return;
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = message;
    container.appendChild(el);
    requestAnimationFrame(() => el.classList.add('toast-visible'));
    setTimeout(() => { el.classList.remove('toast-visible'); setTimeout(() => el.remove(), 300); }, duration);
  },

  dialog: (html, width = 500) => {
    const overlay = Utils.$('#dialog-overlay');
    if (!overlay) return Promise.resolve(null);
    overlay.innerHTML = `<div class="dialog" style="width:${width}px">${html}</div>`;
    overlay.classList.add('dialog-active');
    return new Promise(resolve => {
      const close = (result) => { overlay.classList.remove('dialog-active'); resolve(result); };
      overlay.addEventListener('click', (e) => { if (e.target === overlay) close(null); });
      overlay._close = close;
      overlay.querySelectorAll('[data-close]').forEach(b => b.addEventListener('click', () => close(b.dataset.close)));
      overlay.querySelectorAll('[data-value]').forEach(b => b.addEventListener('click', () => close(b.dataset.value)));
    });
  },

  confirm: (msg) => Utils.dialog(`
    <h3>Confirmare</h3><p>${Utils.escapeHtml(msg)}</p>
    <div class="dialog-buttons">
      <button class="btn btn-secondary" data-close="false">Nu</button>
      <button class="btn btn-primary" data-value="true">Da</button>
    </div>`, 400).then(r => r === 'true'),

  prompt: (msg, defaultValue = '') => Utils.dialog(`
    <h3>${Utils.escapeHtml(msg)}</h3>
    <input id="dialog-input" class="input" value="${Utils.escapeHtml(defaultValue)}" autofocus>
    <div class="dialog-buttons">
      <button class="btn btn-secondary" data-close="null">Anulează</button>
      <button class="btn btn-primary" id="dialog-ok">OK</button>
    </div>`, 400).then(r => {
      if (r === 'null') return null;
      const input = document.getElementById('dialog-input');
      return input ? input.value.trim() : null;
    }),

  parseLyrics: (text) => {
    if (!text) return [];
    const blocks = text.split(/\n\s*\n/).map(b => b.trim()).filter(b => b.length > 0);
    return blocks.length ? blocks : [text.trim()];
  },

  slidesToText: (slides) => Array.isArray(slides) ? slides.join('\n\n') : slides,
  textToSlides: (text) => Utils.parseLyrics(text),

  formatTime: (s) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  },

  groupBy: (arr, key) => {
    return arr.reduce((acc, item) => {
      const k = item[key] || '';
      if (!acc[k]) acc[k] = [];
      acc[k].push(item);
      return acc;
    }, {});
  },

  sacredWords: (text, words, allcaps) => {
    if (!words || !words.length) return text;
    let result = text;
    for (const w of words) {
      const trimmed = w.trim();
      if (!trimmed) continue;
      const re = new RegExp(`\\b${trimmed.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'gi');
      result = result.replace(re, allcaps ? trimmed.toUpperCase() : trimmed);
    }
    return result;
  },

  loadScript: (src) => new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src; s.onload = resolve; s.onerror = reject;
    document.head.appendChild(s);
  }),

  loadCss: (href) => {
    const l = document.createElement('link');
    l.rel = 'stylesheet'; l.href = href;
    document.head.appendChild(l);
  },
};
