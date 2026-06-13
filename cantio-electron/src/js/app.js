(function () {
  let currentServiceId = null;
  let autoAdvanceTimer = null;
  let currentSongId = null;
  let allSongs = [];
  let filteredSongs = [];

  async function init() {
    setupLeftTabs();
    setupCenterTabs();
    setupToolbar();
    setupRightPanel();
    setupServicePanel();
    setupSongListActions();
    setupSlidesArea();
    setupFormattingToolbar();
    setupEditor();
    setupGlobalShortcuts();
    setupStateWatchers();
    setupBibleSearch();
    setupOverlayControls();
    loadBibleBooks();

    const off = window.api.on('profile-loaded', (profile) => {
      appState.setProfile(profile);
      appState.setSettings(profile.settings || {});
      loadInitialData();
    });
    appState.setLoading(true);
  }

  // ── LEFT TABS ──────────────────────────────────────────
  function setupLeftTabs() {
    document.querySelectorAll('.l-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.l-tab').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.l-tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        const tab = document.getElementById('ltab-' + btn.dataset.ltab);
        if (tab) tab.classList.add('active');
      });
    });
  }

  // ── CENTER TABS ────────────────────────────────────────
  function setupCenterTabs() {
    document.querySelectorAll('.c-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.c-tab').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.c-tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        const tab = document.getElementById('ctab-' + btn.dataset.ctab);
        if (tab) tab.classList.add('active');
      });
    });
  }

  // ── TOOLBAR ─────────────────────────────────────────────
  function setupToolbar() {
    const toolbar = document.getElementById('toolbar');
    if (!toolbar) return;
    toolbar.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-action]');
      if (!btn) return;
      handleAction(btn.dataset.action, btn);
    });
    document.getElementById('send-target')?.addEventListener('change', () => {
      appState.set('sendTarget', document.getElementById('send-target').value);
    });
    document.getElementById('btn-profile')?.addEventListener('click', () => openProfileDialog());
    document.getElementById('btn-display')?.addEventListener('click', () => openDisplay());
    document.getElementById('btn-stage')?.addEventListener('click', () => toggleStageMonitor());
  }

  function handleAction(action, btn) {
    switch (action) {
      case 'new-song': newSong(); break;
      case 'open-settings': openSettings(); break;
      case 'save-service': saveService(); break;
      case 'load-service': loadService(); break;
      case 'clear-service': clearService(); break;
      case 'open-media': openMediaFile(); break;
      case 'open-camera': openCamera(); break;
      case 'open-cloud-media': Utils.toast('Cloud media — în dezvoltare', 'info'); break;
      case 'toggle-clock': toggleClock(); break;
    }
  }

  // ── RIGHT PANEL ─────────────────────────────────────────
  function setupRightPanel() {
    document.getElementById('ctrl-golive')?.addEventListener('click', goLive);
    document.getElementById('ctrl-black')?.addEventListener('click', handleBlack);
    document.getElementById('ctrl-clear')?.addEventListener('click', clearText);
    document.getElementById('ctrl-freeze')?.addEventListener('click', toggleFreezeBtn);
    document.getElementById('ctrl-logo')?.addEventListener('click', toggleLogo);
    document.getElementById('ctrl-dual')?.addEventListener('click', toggleDualLang);
    document.getElementById('ctrl-preview')?.addEventListener('click', togglePreview);
    document.getElementById('ctrl-prev')?.addEventListener('click', prevSlide);
    document.getElementById('ctrl-next')?.addEventListener('click', nextSlide);
    document.getElementById('auto-check')?.addEventListener('change', toggleAutoAdvance);
    document.getElementById('ticker-send')?.addEventListener('click', sendTicker);
    document.getElementById('ticker-clear')?.addEventListener('click', clearTicker);
    document.getElementById('ctrl-clock')?.addEventListener('click', toggleClock);
    document.getElementById('countdown-go')?.addEventListener('click', startCountdown);
  }

  // ── SERVICE PANEL ───────────────────────────────────────
  function setupServicePanel() {
    document.getElementById('svc-add')?.addEventListener('click', () => {
      const song = appState.get('currentSong');
      if (song && song.id) addToService(song.id, song.title);
    });
    document.getElementById('svc-up')?.addEventListener('click', () => moveServiceItem(-1));
    document.getElementById('svc-down')?.addEventListener('click', () => moveServiceItem(1));
    document.getElementById('svc-remove')?.addEventListener('click', removeServiceItem);
    document.getElementById('service-list')?.addEventListener('click', (e) => {
      const item = e.target.closest('.service-item');
      if (!item) return;
      const idx = parseInt(item.dataset.index);
      const action = e.target.closest('[data-service-action]');
      if (action) {
        const a = action.dataset.serviceAction;
        if (a === 'go') loadServiceSong(idx);
        else if (a === 'up') moveServiceItemAt(idx, -1);
        else if (a === 'down') moveServiceItemAt(idx, 1);
        else if (a === 'remove') removeServiceItemAt(idx);
      } else {
        loadServiceSong(idx);
      }
    });
  }

  function renderServiceList() {
    const el = document.getElementById('service-list');
    if (!el) return;
    const items = appState.get('serviceItems');
    if (!items || !items.length) {
      el.innerHTML = '<div class="empty-state">Lista de serviciu este goală</div>';
      return;
    }
    el.innerHTML = items.map((item, i) => {
      const isCurrent = currentSongId && item.item_id === currentSongId;
      return `<div class="service-item ${isCurrent ? 'selected' : ''} ${isCurrent ? 'live' : ''}" data-index="${i}">
        <span class="service-num">${i + 1}.</span>
        <span class="service-title">${Utils.escapeHtml(item.title || '')}</span>
        <span class="service-actions" style="float:right">
          <button class="btn-icon" data-service-action="go" data-index="${i}" title="Trimite">▶</button>
          <button class="btn-icon" data-service-action="up" data-index="${i}" title="Sus">↑</button>
          <button class="btn-icon" data-service-action="down" data-index="${i}" title="Jos">↓</button>
          <button class="btn-icon" data-service-action="remove" data-index="${i}" title="Șterge">✕</button>
        </span>
      </div>`;
    }).join('');
  }

  function loadServiceSong(idx) {
    const items = appState.get('serviceItems');
    const item = items[idx];
    if (!item) return;
    if (item.item_id) {
      loadSongById(item.item_id);
    }
  }

  function moveServiceItem(dir) {
    // not implemented - keyboard selection would need focus tracking
  }

  function moveServiceItemAt(idx, dir) {
    const items = [...appState.get('serviceItems')];
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= items.length) return;
    [items[idx], items[newIdx]] = [items[newIdx], items[idx]];
    appState.set('serviceItems', items);
    renderServiceList();
    if (currentServiceId) DB.service.saveItems(currentServiceId, items);
  }

  function removeServiceItemAt(idx) {
    let items = [...appState.get('serviceItems')];
    items.splice(idx, 1);
    appState.set('serviceItems', items);
    renderServiceList();
    if (currentServiceId) DB.service.saveItems(currentServiceId, items);
  }

  function removeServiceItem() {
    // find selected
  }

  async function addToService(songId, title) {
    const items = appState.get('serviceItems');
    const newItem = { item_type: 'song', item_id: songId, title, notes: '', theme: '', duration_seconds: 0 };
    items.push(newItem);
    appState.set('serviceItems', items);
    renderServiceList();
    if (currentServiceId) await DB.service.saveItems(currentServiceId, items);
  }

  // ── SONG LIST ───────────────────────────────────────────
  function setupSongListActions() {
    document.getElementById('sng-edit')?.addEventListener('click', () => {
      const sel = document.querySelector('.song-item.selected');
      if (sel) loadSongById(parseInt(sel.dataset.id));
    });
    document.getElementById('sng-delete')?.addEventListener('click', async () => {
      const sel = document.querySelector('.song-item.selected');
      if (!sel) return;
      const id = parseInt(sel.dataset.id);
      const song = allSongs.find(s => s.id === id);
      if (!song) return;
      const ok = await Utils.confirm('Ștergi "' + song.title + '"?');
      if (ok) {
        await DB.songs.delete(id);
        allSongs = allSongs.filter(s => s.id !== id);
        doSearch();
        Utils.toast('Cântare ștearsă', 'info');
      }
    });
    document.getElementById('sng-add-svc')?.addEventListener('click', () => {
      const sel = document.querySelector('.song-item.selected');
      if (!sel) return;
      const id = parseInt(sel.dataset.id);
      const song = allSongs.find(s => s.id === id);
      if (song) addToService(id, song.title);
    });
    document.getElementById('search-input')?.addEventListener('input', Utils.debounce(() => doSearch(), 200));
    document.getElementById('category-filter')?.addEventListener('change', () => doSearch());
  }

  function renderSongList() {
    const el = document.getElementById('song-list');
    if (!el) return;
    if (!filteredSongs.length) {
      el.innerHTML = '<div class="empty-state">Nu există cântări. Adaugă prima cântare!</div>';
      return;
    }
    el.innerHTML = filteredSongs.map(song => {
      const isCurrent = currentSongId === song.id;
      const author = song.author ? `<span class="author">${Utils.escapeHtml(song.author)}</span>` : '';
      return `<div class="song-item ${isCurrent ? 'selected' : ''}" data-id="${song.id}">
        <span class="title">${Utils.escapeHtml(song.title)}</span>
        ${author}
      </div>`;
    }).join('');
    el.querySelectorAll('.song-item').forEach(item => {
      item.addEventListener('click', () => {
        const id = parseInt(item.dataset.id);
        loadSongById(id);
      });
      item.addEventListener('dblclick', () => {
        const id = parseInt(item.dataset.id);
        loadSongById(id);
        setTimeout(goLive, 100);
      });
    });
  }

  async function loadSongById(id) {
    try {
      const song = await DB.songs.getById(id);
      if (!song) return;
      currentSongId = song.id;
      appState.setCurrentSong(song);
      let slides = [];
      try { slides = JSON.parse(song.slides || '[]'); } catch {}
      if (!slides.length && song.lyrics) {
        slides = Utils.parseLyrics(song.lyrics);
      }
      appState.setSlides(slides);
      document.getElementById('song-title-edit').value = song.title || '';
      document.getElementById('song-editor').value = slides.join('\n\n');
      document.getElementById('slide-count').textContent = slides.length + ' slide-uri';
      updateWordCounter();
      renderSlidesGrid();
      document.querySelectorAll('.song-item').forEach(el => el.classList.remove('selected'));
      const sel = document.querySelector(`.song-item[data-id="${id}"]`);
      if (sel) sel.classList.add('selected');
      document.getElementById('st-song').textContent = song.title;
    } catch (e) {
      console.error('Load song error:', e);
    }
  }

  async function loadSongs() {
    try {
      const songs = await DB.songs.getAll(0, 500);
      allSongs = songs || [];
      filteredSongs = [...allSongs];
      renderSongList();
      updateCategoryFilter();
    } catch (e) {
      console.error('Load songs error:', e);
    }
  }

  function doSearch() {
    const query = (document.getElementById('search-input')?.value || '').toLowerCase();
    const cat = document.getElementById('category-filter')?.value || '';
    filteredSongs = allSongs.filter(s => {
      if (query && !s.title.toLowerCase().includes(query) && !(s.author || '').toLowerCase().includes(query)) return false;
      if (cat && s.category !== cat) return false;
      return true;
    });
    renderSongList();
  }

  function updateCategoryFilter() {
    const sel = document.getElementById('category-filter');
    if (!sel) return;
    const cats = [...new Set(allSongs.map(s => s.category).filter(Boolean))];
    sel.innerHTML = '<option value="">Toate categoriile</option>' +
      cats.map(c => `<option value="${Utils.escapeHtml(c)}">${Utils.escapeHtml(c)}</option>`).join('');
  }

  function newSong() {
    currentSongId = null;
    appState.setCurrentSong({ title: '', author: '', category: '', lyrics: '', slides: '[]', id: null });
    appState.setSlides([]);
    document.getElementById('song-title-edit').value = '';
    document.getElementById('song-editor').value = '';
    document.getElementById('slide-count').textContent = '0 slide-uri';
    document.getElementById('st-song').textContent = 'Nicio cântare încărcată';
    updateWordCounter();
    renderSlidesGrid();
    document.getElementById('song-title-edit')?.focus();
  }

  // ── SLIDES AREA ─────────────────────────────────────────
  function setupSlidesArea() {
    document.getElementById('thumb-minus')?.addEventListener('click', () => {
      const grid = document.getElementById('slides-grid');
      const cur = parseInt(grid.dataset.thumbSize || '160');
      const nxt = Math.max(80, cur - 20);
      grid.dataset.thumbSize = nxt;
      grid.style.gridTemplateColumns = `repeat(auto-fill, minmax(${nxt}px, 1fr))`;
      document.getElementById('thumb-size').textContent = ['XS','S','M','L','XL'][Math.round((nxt-80)/40)] || 'S';
    });
    document.getElementById('thumb-plus')?.addEventListener('click', () => {
      const grid = document.getElementById('slides-grid');
      const cur = parseInt(grid.dataset.thumbSize || '160');
      const nxt = Math.min(300, cur + 20);
      grid.dataset.thumbSize = nxt;
      grid.style.gridTemplateColumns = `repeat(auto-fill, minmax(${nxt}px, 1fr))`;
      document.getElementById('thumb-size').textContent = ['XS','S','M','L','XL'][Math.round((nxt-80)/40)] || 'S';
    });
    document.getElementById('view-toggle')?.addEventListener('click', () => {
      const grid = document.getElementById('slides-grid');
      const list = document.getElementById('slides-list');
      const ph = document.getElementById('slides-placeholder');
      if (grid.style.display !== 'none') {
        grid.style.display = 'none';
        list.style.display = 'grid';
        renderSlidesList();
      } else {
        grid.style.display = 'grid';
        list.style.display = 'none';
      }
    });
    document.getElementById('btn-reorder')?.addEventListener('click', () => {
      Utils.toast('Trage slide-urile pentru reordonare', 'info');
    });
  }

  function renderSlidesGrid() {
    const grid = document.getElementById('slides-grid');
    const ph = document.getElementById('slides-placeholder');
    const slides = appState.get('slides');
    const idx = appState.get('currentSlide');
    if (!slides || !slides.length) {
      grid.innerHTML = '';
      ph.style.display = 'flex';
      return;
    }
    ph.style.display = 'none';
    grid.innerHTML = slides.map((slide, i) => {
      const text = slide.split('\n').slice(0, 3).join('\n');
      return `<div class="slide-card ${i === idx ? 'active' : ''}" data-index="${i}">${Utils.escapeHtml(text) || '(gol)'}</div>`;
    }).join('');
    grid.querySelectorAll('.slide-card').forEach(card => {
      card.addEventListener('click', () => {
        const i = parseInt(card.dataset.index);
        appState.setCurrentSlide(i);
        renderSlidesGrid();
      });
      card.addEventListener('dblclick', () => {
        const i = parseInt(card.dataset.index);
        appState.setCurrentSlide(i);
        renderSlidesGrid();
        goLive();
      });
    });
  }

  function renderSlidesList() {
    const list = document.getElementById('slides-list');
    const slides = appState.get('slides');
    const idx = appState.get('currentSlide');
    if (!list) return;
    if (!slides || !slides.length) { list.innerHTML = ''; return; }
    list.innerHTML = slides.map((slide, i) =>
      `<div class="slide-card ${i === idx ? 'active' : ''}" data-index="${i}">
        <strong>${i + 1}.</strong> ${Utils.escapeHtml(slide.split('\n')[0] || '')}
      </div>`
    ).join('');
  }

  // ── SONG EDITOR ─────────────────────────────────────────
  function setupEditor() {
    document.getElementById('song-title-edit')?.addEventListener('input', () => {
      const song = appState.get('currentSong');
      if (song) { song.title = document.getElementById('song-title-edit').value; appState.setCurrentSong(song); }
    });
    document.getElementById('btn-save-song')?.addEventListener('click', saveCurrentSong);
    document.getElementById('btn-new-slide')?.addEventListener('click', () => {
      const editor = document.getElementById('song-editor');
      if (editor) { if (editor.value) editor.value += '\n\n'; editor.focus(); }
    });
    document.getElementById('editor-collapse')?.addEventListener('click', () => {
      const wrap = document.querySelector('.editor-wrap');
      const editorHdr = document.querySelector('.editor-hdr');
      if (wrap) {
        const isCollapsed = wrap.dataset.collapsed === 'true';
        wrap.dataset.collapsed = !isCollapsed;
        wrap.style.minHeight = isCollapsed ? '120px' : '30px';
        document.getElementById('editor-collapse').textContent = isCollapsed ? '▼' : '▲';
        if (!isCollapsed) {
          wrap.querySelectorAll('.fmt-toolbar, .fmt-status, .song-editor, .word-counter').forEach(el => el.style.display = 'none');
        } else {
          wrap.querySelectorAll('.fmt-toolbar, .fmt-status, .song-editor, .word-counter').forEach(el => el.style.display = '');
        }
      }
    });
  }

  function setupFormattingToolbar() {
    const editor = document.getElementById('song-editor');
    editor?.addEventListener('input', () => onEditorChange());

    document.getElementById('fmt-bold')?.addEventListener('click', () => insertFmt('**', '**'));
    document.getElementById('fmt-italic')?.addEventListener('click', () => insertFmt('*', '*'));
    document.getElementById('fmt-underline')?.addEventListener('click', () => insertFmt('<u>', '</u>'));
    document.getElementById('fmt-strike')?.addEventListener('click', () => insertFmt('~~', '~~'));
    document.getElementById('fmt-clear')?.addEventListener('click', () => {
      const editor = document.getElementById('song-editor');
      if (!editor) return;
      const sel = editor.selectionStart;
      editor.value = editor.value.replace(/[*_~`<>/]/g, '');
    });
    document.getElementById('fmt-align-left')?.addEventListener('click', () => {});
    document.getElementById('fmt-align-center')?.addEventListener('click', () => {});
    document.getElementById('fmt-align-right')?.addEventListener('click', () => {});
    document.getElementById('fmt-undo')?.addEventListener('click', () => document.execCommand('undo'));
    document.getElementById('fmt-redo')?.addEventListener('click', () => document.execCommand('redo'));
    document.getElementById('fmt-reset')?.addEventListener('click', () => {
      document.getElementById('fmt-status-lbl').textContent = 'Folosește setările globale';
      document.getElementById('fmt-reset').style.display = 'none';
    });
    document.getElementById('fmt-translate')?.addEventListener('click', () => {
      const text = document.getElementById('song-editor')?.value;
      if (text) translateLyrics(text);
    });
  }

  function insertFmt(before, after) {
    const editor = document.getElementById('song-editor');
    if (!editor) return;
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    const text = editor.value;
    const selected = text.substring(start, end);
    editor.value = text.substring(0, start) + before + selected + after + text.substring(end);
    editor.focus();
    editor.selectionStart = start + before.length;
    editor.selectionEnd = start + before.length + selected.length;
  }

  function onEditorChange() {
    const editor = document.getElementById('song-editor');
    if (!editor) return;
    const text = editor.value;
    const slides = Utils.parseLyrics(text);
    appState.setSlides(slides);
    document.getElementById('slide-count').textContent = slides.length + ' slide-uri';
    updateWordCounter();
    renderSlidesGrid();
  }

  function updateWordCounter() {
    const el = document.getElementById('word-counter');
    const editor = document.getElementById('song-editor');
    if (!el || !editor) return;
    const text = editor.value;
    const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
    const slides = Utils.parseLyrics(text).length;
    el.textContent = words + ' cuvinte • ' + slides + ' slide-uri';
  }

  async function saveCurrentSong() {
    const song = appState.get('currentSong');
    const slides = appState.get('slides');
    const title = document.getElementById('song-title-edit')?.value || '';
    if (!song) return;
    song.title = title || song.title;
    song.slides = JSON.stringify(slides);
    song.lyrics = slides.join('\n\n');
    const id = await DB.songs.save(song);
    if (id) {
      song.id = id;
      currentSongId = id;
      appState.setCurrentSong(song);
      // Refresh the song in allSongs
      const existing = allSongs.findIndex(s => s.id === id);
      if (existing >= 0) allSongs[existing] = { ...song };
      else allSongs.push(song);
      doSearch();
      Utils.toast('Cântare salvată', 'success');
    }
  }

  // ── BIBLE ───────────────────────────────────────────────
  let bibleBooks = [];
  let bibleCurrentTrans = 'niv';

  async function loadBibleBooks() {
    try {
      let books = await DB.bible.getBooks(bibleCurrentTrans);
      if (!books || !books.length) books = await DB.bible.getDefaultBooks();
      bibleBooks = books || [];
      // Show all verses as searchable list
    } catch (e) {
      console.error('Load bible books error:', e);
    }
  }

  function setupBibleSearch() {
    document.getElementById('bible-search')?.addEventListener('input', Utils.debounce(() => doBibleSearch(), 300));
  }

  async function doBibleSearch() {
    const input = document.getElementById('bible-search');
    const el = document.getElementById('bible-verses');
    if (!input || !el) return;
    const query = input.value.trim();
    if (!query) { el.innerHTML = '<div class="empty-state">Introdu un termen de căutare</div>'; return; }
    try {
      const results = await DB.bible.search(query, bibleCurrentTrans);
      if (!results || !results.length) {
        el.innerHTML = '<div class="empty-state">Niciun rezultat</div>';
        return;
      }
      el.innerHTML = results.map(r =>
        `<div class="verse-item" data-book="${r.book_id}" data-chapter="${r.chapter}" data-verse="${r.verse}">
          <span class="v-num">${r.book_name} ${r.chapter}:${r.verse}</span>
          <span>${Utils.escapeHtml(r.text)}</span>
        </div>`
      ).join('');
      el.querySelectorAll('.verse-item').forEach(item => {
        item.addEventListener('dblclick', async () => {
          const b = parseInt(item.dataset.book);
          const c = parseInt(item.dataset.chapter);
          const v = parseInt(item.dataset.verse);
          const verse = await DB.bible.getVerse(b, c, v, bibleCurrentTrans);
          if (verse) {
            const text = verse.book_name + ' ' + c + ':' + v + '\n' + verse.text;
            const editor = document.getElementById('song-editor');
            if (editor) {
              if (editor.value) editor.value += '\n\n';
              editor.value += text;
              onEditorChange();
            }
          }
        });
      });
    } catch (e) {
      console.error('Bible search error:', e);
    }
  }

  // ── OVERLAY CONTROLS ────────────────────────────────────
  function setupOverlayControls() {
    document.getElementById('ov-ticker-send')?.addEventListener('click', () => {
      const input = document.getElementById('overlay-ticker-input');
      if (input && input.value.trim()) {
        window.api.display.ticker({ text: input.value.trim(), speed: 2.5, color: '#f9e2af' });
        appState.set('tickerText', input.value.trim());
        Utils.toast('Ticker trimis', 'success');
      }
    });
    document.getElementById('ov-ticker-clear')?.addEventListener('click', async () => {
      await window.api.display.hideTicker();
      appState.set('tickerText', '');
    });
    document.getElementById('ov-timer-start')?.addEventListener('click', () => {
      const sec = parseInt(document.getElementById('ov-timer')?.value || '60');
      window.api.display.timer({ seconds: sec, color: '#a6e3a1' });
      appState.set('showTimer', true);
    });
  }

  // ── GO LIVE ─────────────────────────────────────────────
  async function goLive() {
    const song = appState.get('currentSong');
    const slideIdx = appState.get('currentSlide');
    const slides = appState.get('slides');
    if (!slides || !slides.length) { Utils.toast('Nicio cântare selectată', 'warning'); return; }
    const text = slides[slideIdx] || '';
    const settings = appState.get('settings');
    const metadata = {
      title: song ? song.title : '',
      author: song ? song.author : '',
      category: song ? song.category : '',
      source: 'song',
    };
    try {
      await window.api.display.show({ screenIndex: 0, text, metadata, transition: settings.transition || 'crossfade' });
      appState.setLiveSlide({ text, slideIndex: slideIdx, song });
      appState.set('isLive', true);
      const dot = document.getElementById('st-live-dot');
      if (dot) { dot.classList.add('active'); }
      pushStageState();
      if (appState.get('autoAdvance')) startAutoAdvance();
    } catch (e) {
      Utils.toast('Eroare la trimiterea pe ecran', 'error');
    }
  }

  function nextSlide() {
    const slides = appState.get('slides');
    const idx = appState.get('currentSlide');
    if (idx < slides.length - 1) {
      appState.setCurrentSlide(idx + 1);
      renderSlidesGrid();
      if (appState.get('isLive')) goLive();
    }
  }

  function prevSlide() {
    const idx = appState.get('currentSlide');
    if (idx > 0) {
      appState.setCurrentSlide(idx - 1);
      renderSlidesGrid();
      if (appState.get('isLive')) goLive();
    }
  }

  function startAutoAdvance() {
    stopAutoAdvance();
    const delay = (parseInt(appState.get('settings').autoAdvanceDelay) || 5) * 1000;
    autoAdvanceTimer = setInterval(() => {
      const slides = appState.get('slides');
      const idx = appState.get('currentSlide');
      if (idx < slides.length - 1) nextSlide();
      else stopAutoAdvance();
    }, delay);
  }

  function stopAutoAdvance() {
    if (autoAdvanceTimer) { clearInterval(autoAdvanceTimer); autoAdvanceTimer = null; }
  }

  async function handleBlack() {
    try {
      await window.api.display.black({ screenIndex: 0 });
      appState.set('isLive', false);
    } catch (e) { Utils.toast('Eroare ecran negru', 'error'); }
  }

  async function clearText() {
    try {
      await window.api.display.clearText({ screenIndex: 0 });
      appState.set('isLive', false);
    } catch (e) {}
  }

  async function toggleFreezeBtn() {
    const frozen = appState.get('isFrozen');
    appState.set('isFrozen', !frozen);
    await window.api.display.freeze({ freeze: !frozen });
    document.getElementById('ctrl-freeze').classList.toggle('active', !frozen);
  }

  async function toggleLogo() {
    const show = appState.get('showLogo');
    appState.set('showLogo', !show);
    if (!show) {
      const logoPath = appState.get('settings').logoPath || '';
      if (logoPath) await window.api.display.logo({ path: logoPath });
      else Utils.toast('Setează o cale pentru logo în setări', 'warning');
    } else {
      await window.api.display.hideLogo();
    }
    document.getElementById('ctrl-logo').classList.toggle('active', !show);
  }

  async function toggleClock() {
    const show = appState.get('showClock');
    appState.set('showClock', !show);
    await window.api.display.clock({ active: !show, color: '#ffffff', format: 'HH:MM:SS' });
    document.getElementById('ctrl-clock').classList.toggle('active', !show);
  }

  function toggleDualLang() {
    const dual = appState.get('dualLanguage');
    appState.set('dualLanguage', !dual);
    document.getElementById('ctrl-dual').classList.toggle('active', !dual);
    if (!dual && appState.get('translationText')) {
      window.api.display.show({ screenIndex: 0, text: appState.get('translationText'), transition: 'crossfade' });
    }
  }

  function togglePreview() {
    const btn = document.getElementById('ctrl-preview');
    btn.classList.toggle('active');
  }

  function sendTicker() {
    const input = document.getElementById('ticker-input');
    if (input && input.value.trim()) {
      window.api.display.ticker({ text: input.value.trim(), speed: 2.5, color: '#f9e2af' });
      appState.set('tickerText', input.value.trim());
      Utils.toast('Ticker trimis', 'success');
    }
  }

  function startCountdown() {
    const sec = parseInt(document.getElementById('countdown-spin')?.value || '300');
    window.api.display.timer({ seconds: sec, color: '#a6e3a1' });
    appState.set('showTimer', true);
  }

  function toggleAutoAdvance() {
    const v = document.getElementById('auto-check').checked;
    appState.set('autoAdvance', v);
    if (v) { if (appState.get('isLive')) startAutoAdvance(); }
    else stopAutoAdvance();
  }

  // ── STAGE MONITOR ───────────────────────────────────────
  function pushStageState() {
    const slides = appState.get('slides');
    const idx = appState.get('currentSlide');
    const song = appState.get('currentSong');
    window.api.stage.send({
      currentSlide: slides[idx],
      nextSlide: slides[idx + 1] || '',
      previousSlide: slides[idx - 1] || '',
      slideIndex: idx,
      totalSlides: slides.length,
      songTitle: song ? song.title : '',
      songAuthor: song ? song.author : '',
    });
  }

  async function toggleStageMonitor() {
    try {
      await window.api.stage.open();
      document.getElementById('btn-stage').className = 'tb-btn tb-open';
    } catch {
      await window.api.stage.close();
      document.getElementById('btn-stage').className = 'tb-btn tb-closed';
    }
  }

  // ── REMOTE ──────────────────────────────────────────────
  async function toggleRemote() {
    if (appState.get('remoteRunning')) {
      await window.api.remote.stop();
      appState.set('remoteRunning', false);
      appState.set('remoteUrl', null);
      Utils.toast('Server remote oprit', 'info');
    } else {
      const result = await window.api.remote.start({ port: 5050 });
      appState.set('remoteRunning', true);
      appState.set('remoteUrl', result);
      Utils.toast('Server remote pornit: ' + result, 'success');
    }
  }

  // ── SERVICE SAVE/LOAD ──────────────────────────────────
  async function saveService() {
    const result = await window.api.dialog.saveFile({
      title: 'Salvează serviciu', defaultPath: 'serviciu.gps',
      filters: [{ name: 'Cantio Service', extensions: ['gps'] }],
    });
    if (result.canceled || !result.filePath) return;
    const items = appState.get('serviceItems');
    await window.api.service.save({ path: result.filePath, items });
    Utils.toast('Serviciu salvat', 'success');
  }

  async function loadService() {
    const result = await window.api.dialog.openFile({
      title: 'Deschide serviciu', filters: [{ name: 'Cantio Service', extensions: ['gps'] }],
    });
    if (result.canceled || !result.filePaths.length) return;
    const data = await window.api.service.load(result.filePaths[0]);
    if (data.items) {
      appState.set('serviceItems', data.items);
      renderServiceList();
      Utils.toast('Serviciu încărcat: ' + data.items.length + ' elemente', 'success');
    }
  }

  function clearService() {
    Utils.confirm('Ștergi toate elementele din lista de serviciu?').then(async (ok) => {
      if (ok) {
        appState.set('serviceItems', []);
        if (currentServiceId) await DB.service.clear(currentServiceId);
        renderServiceList();
      }
    });
  }

  // ── MEDIA ───────────────────────────────────────────────
  async function openMediaFile() {
    const result = await window.api.dialog.openFile({
      title: 'Selectează fișier video', properties: ['openFile'],
      filters: [{ name: 'Media', extensions: ['mp4','avi','mov','mkv','webm','png','jpg','gif'] }],
    });
    if (result.canceled || !result.filePaths.length) return;
    const fp = result.filePaths[0];
    const ext = fp.split('.').pop().toLowerCase();
    if (['mp4','avi','mov','mkv','webm'].includes(ext)) {
      await window.api.media.startVideo(fp);
    } else {
      await window.api.display.logo({ path: fp });
    }
  }

  async function openCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      Utils.toast('Cameră activată', 'success');
      const video = document.createElement('video');
      video.srcObject = stream; video.play();
      const canvas = document.createElement('canvas');
      canvas.width = 640; canvas.height = 360;
      const ctx = canvas.getContext('2d');
      function capture() {
        if (video.readyState >= 2) {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          window.api.display.show({ screenIndex: 0, text: '', metadata: { imageData: canvas.toDataURL('image/jpeg', 0.5) }, transition: 'instant' });
        }
        requestAnimationFrame(capture);
      }
      capture();
    } catch (e) { Utils.toast('Eroare cameră: ' + e.message, 'error'); }
  }

  // ── TRANSLATION ─────────────────────────────────────────
  async function translateLyrics(text) {
    try {
      const result = await window.api.translate({ text, targetLang: 'ro' });
      if (result && result.translated) {
        appState.set('translationText', result.translated);
        Utils.toast('Traducere primită', 'success');
      }
    } catch (e) { Utils.toast('Eroare traducere: ' + e.message, 'error'); }
  }

  // ── DISPLAYS ────────────────────────────────────────────
  async function openDisplay() {
    const screens = await window.api.display.getScreens();
    if (!screens.length) { Utils.toast('Niciun ecran disponibil', 'error'); return; }
    const result = await window.api.display.open({ screenIndex: 0 });
    if (result) {
      document.getElementById('btn-display').className = 'tb-btn tb-open';
      document.getElementById('st-display').textContent = 'Display deschis';
    }
  }

  async function closeAllDisplays() {
    await window.api.display.closeAll();
    document.getElementById('btn-display').className = 'tb-btn tb-closed';
    document.getElementById('st-display').textContent = 'Niciun display deschis';
    Utils.toast('Toate display-urile închise', 'info');
  }

  // ── DIALOGS ─────────────────────────────────────────────
  function openSettings() {
    if (typeof Dialogs !== 'undefined' && Dialogs.settings) Dialogs.settings.open();
  }

  function openProfileDialog() {
    if (typeof Dialogs !== 'undefined' && Dialogs.profile) Dialogs.profile.open();
  }

  function openAbout() {
    if (typeof Dialogs !== 'undefined' && Dialogs.about) Dialogs.about.open();
  }

  function openImportDialog() {
    if (typeof Dialogs !== 'undefined' && Dialogs.importDialog) Dialogs.importDialog.open();
  }

  // ── GLOBAL SHORTCUTS ────────────────────────────────────
  function setupGlobalShortcuts() {
    document.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.key === 'F5') { e.preventDefault(); goLive(); }
      if (e.key === ' ' && !e.ctrlKey) { e.preventDefault(); nextSlide(); }
      if (e.key === 'Backspace' && !e.ctrlKey) { e.preventDefault(); prevSlide(); }
      if (e.key === 'Escape') { document.activeElement?.blur(); }
      if (e.key === 'b' || e.key === 'B') { handleBlack(); }
      if (e.key === 's' && e.ctrlKey) { e.preventDefault(); saveCurrentSong(); }
      if (e.key === 'n' && e.ctrlKey) { e.preventDefault(); newSong(); }
      if (e.key === 'f' && e.ctrlKey) { e.preventDefault(); document.getElementById('search-input')?.focus(); }
      if (e.key === 'F11') { e.preventDefault(); window.api.window.fullscreen(!document.fullscreenElement); }
      if (e.key === 'p' && e.ctrlKey) { e.preventDefault(); openSettings(); }
    });
    window.api.on('shortcut-triggered', (command) => {
      if (command === 'go-live') goLive();
      else if (command === 'next-slide') nextSlide();
      else if (command === 'prev-slide') prevSlide();
      else if (command === 'black') handleBlack();
      else if (command === 'freeze') toggleFreezeBtn();
    });
    window.api.on('remote-command', (cmd) => {
      if (cmd === 'next') nextSlide();
      else if (cmd === 'prev') prevSlide();
      else if (cmd === 'black') handleBlack();
      else if (cmd === 'go') goLive();
    });
  }

  // ── STATE WATCHERS ──────────────────────────────────────
  function setupStateWatchers() {
    appState.watch('currentSlide', (idx) => {
      renderSlidesGrid();
      updateSlideNav();
      pushStageState();
      document.getElementById('st-slide').textContent = (idx + 1) + '/' + (appState.get('slides')?.length || 0);
    });
    appState.watch('serviceItems', () => renderServiceList());
    appState.watch('isLive', (v) => {
      const dot = document.getElementById('st-live-dot');
      if (dot) dot.classList.toggle('active', v);
      const liveBtn = document.getElementById('ctrl-golive');
      if (liveBtn) liveBtn.textContent = v ? '● LIVE' : '▶ GO LIVE';
    });
    appState.watch('tickerText', (t) => {
      const status = document.getElementById('st-warnings');
      if (status) status.textContent = t ? '📝 Ticker activ' : '';
    });
    appState.watch('currentSong', (song) => {
      if (song && song.title) {
        document.getElementById('st-song').textContent = song.title;
      }
    });
  }

  function updateSlideNav() {
    const slides = appState.get('slides');
    const idx = appState.get('currentSlide');
    document.getElementById('ctrl-prev').disabled = idx <= 0;
    document.getElementById('ctrl-next').disabled = idx >= slides.length - 1;
  }

  // ── PREVIEW (canvas) ────────────────────────────────────
  function drawPreview() {
    const canvas = document.getElementById('preview-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const slides = appState.get('slides');
    const idx = appState.get('currentSlide');
    const W = canvas.width, H = canvas.height;
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
    if (!slides || !slides.length) {
      ctx.fillStyle = '#555'; ctx.font = '14px sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText('Nicio cântare selectată', W/2, H/2);
      return;
    }
    const text = slides[idx] || '';
    const s = appState.get('settings');
    const size = Math.min(18, Math.floor(H * 0.08));
    const color = s.text_color || '#ffffff';
    ctx.fillStyle = color;
    ctx.font = size + 'px ' + (s.font_family || 'Arial');
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    const lines = text.split('\n').filter(l => l.trim());
    const lineH = size * 1.3;
    const startY = (H - lines.length * lineH) / 2;
    lines.forEach((line, i) => {
      ctx.fillText(line, W/2, startY + i * lineH);
    });
  }

  // ── LOAD INITIAL DATA ──────────────────────────────────
  async function loadInitialData() {
    try {
      const [categories, count] = await Promise.all([
        DB.songs.getCategories(),
        DB.songs.getCount(),
      ]);
      appState.set('categories', categories);
      appState.set('songCount', count);
      await loadSongs();

      const books = await DB.bible.getDefaultBooks();
      appState.set('bibleBooks', books);

      appState.setLoading(false);
      const splash = document.getElementById('splash');
      if (splash) { splash.classList.add('hidden'); setTimeout(() => splash.remove(), 500); }
    } catch (e) {
      console.error('Load error:', e);
      appState.setLoading(false);
      Utils.toast('Eroare încărcare date: ' + e.message, 'error');
      const splash = document.getElementById('splash');
      if (splash) { splash.classList.add('hidden'); setTimeout(() => splash.remove(), 500); }
    }
  }

  // ── INIT ────────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
