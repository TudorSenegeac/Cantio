// Cantio — i18n pentru ferestrele Electron (editor fundal etc.)
// ============================================================
// Traduce DOM-ul (text, butoane, optiuni, placeholder-e, titluri, tooltip-uri)
// in limba activa, folosind ACELEASI pachete de limba ca restul aplicatiei
// (langpacks/<lang>.json livrate + ~/Cantio/i18n/<lang>.json cache utilizator).
// Textele generate dinamic (panoul de proprietati) sunt prinse printr-un
// MutationObserver. Limba romana (sau lipsa pachetului) = nicio schimbare.
//
// Folosire in HTML:  <script src="i18n.js"></script>  apoi  window.I18N.init();

(function () {
  const I18N = { lang: 'ro', map: {}, ready: false };

  let _fs = null, _path = null, _os = null;
  try { _fs = require('fs'); _path = require('path'); _os = require('os'); } catch (e) {}

  function _readJson(p) {
    try { return JSON.parse(_fs.readFileSync(p, 'utf-8')); } catch (e) { return null; }
  }

  function _activeLang() {
    // 1) query ?lang=xx  2) fisierul scris de Python  3) 'ro'
    try {
      const q = new URLSearchParams(location.search).get('lang');
      if (q) return q;
    } catch (e) {}
    if (_fs && _os) {
      try {
        const f = _path.join(_os.homedir(), 'Cantio', 'i18n', '_active_lang.txt');
        const v = _fs.readFileSync(f, 'utf-8').trim();
        if (v) return v;
      } catch (e) {}
    }
    return 'ro';
  }

  function _loadMap(lang) {
    const map = {};
    if (!_fs || !_path || !_os) return map;
    // pachet livrat: cauta in mai multe locuri (sursa + build)
    const cands = [
      _path.join(__dirname, '..', 'langpacks', lang + '.json'),
      _path.join(__dirname, 'langpacks', lang + '.json'),
      _path.join(process.resourcesPath || '', 'langpacks', lang + '.json'),
    ];
    for (const c of cands) {
      const d = _readJson(c);
      if (d) { Object.assign(map, d); break; }
    }
    // cache utilizator (suprascrie)
    const u = _readJson(_path.join(_os.homedir(), 'Cantio', 'i18n', lang + '.json'));
    if (u) Object.assign(map, u);
    return map;
  }

  function t(s) {
    if (s == null) return s;
    const key = String(s).trim();
    if (!key) return s;
    const tr = I18N.map[key];
    if (tr == null) return s;
    // pastram spatiile din jur
    return String(s).replace(key, tr);
  }

  function _translateTextNode(node) {
    const raw = node.nodeValue;
    if (!raw || !raw.trim()) return;
    const key = raw.trim();
    const tr = I18N.map[key];
    if (tr != null && tr !== key) {
      if (node.__i18n_src == null) node.__i18n_src = raw;
      node.nodeValue = raw.replace(key, tr);
    }
  }

  function _translateAttr(el, attr) {
    const v = el.getAttribute(attr);
    if (!v || !v.trim()) return;
    const key = v.trim();
    const tr = I18N.map[key];
    if (tr != null && tr !== key) {
      const prop = '__i18n_' + attr;
      if (el[prop] == null) el[prop] = v;
      el.setAttribute(attr, v.replace(key, tr));
    }
  }

  function translateDOM(root) {
    if (I18N.lang === 'ro') return;
    root = root || document.body;
    if (!root) return;
    // text nodes
    try {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
      const nodes = [];
      let n;
      while ((n = walker.nextNode())) nodes.push(n);
      nodes.forEach(_translateTextNode);
    } catch (e) {}
    // atribute (placeholder / title)
    try {
      const els = root.querySelectorAll('[placeholder], [title]');
      els.forEach(el => { _translateAttr(el, 'placeholder'); _translateAttr(el, 'title'); });
      if (root.getAttribute) { _translateAttr(root, 'placeholder'); _translateAttr(root, 'title'); }
    } catch (e) {}
  }

  let _pending = null;
  function _observe() {
    try {
      const obs = new MutationObserver((muts) => {
        if (_pending) return;
        _pending = setTimeout(() => {
          _pending = null;
          try { translateDOM(document.body); } catch (e) {}
        }, 60);
      });
      obs.observe(document.body, { childList: true, subtree: true, characterData: true });
    } catch (e) {}
  }

  I18N.init = function () {
    I18N.lang = _activeLang();
    if (I18N.lang && I18N.lang !== 'ro') {
      I18N.map = _loadMap(I18N.lang);
    }
    I18N.ready = true;
    if (I18N.lang === 'ro') return;   // nimic de tradus
    const run = () => { translateDOM(document.body); _observe(); };
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', run);
    } else {
      run();
    }
  };

  I18N.t = t;
  I18N.translateDOM = translateDOM;
  window.I18N = I18N;
})();
