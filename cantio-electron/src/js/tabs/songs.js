const Tabs = Tabs || {};
Tabs.songs = {
  _currentPage: 0,
  _allSongs: [],
  _filteredSongs: [],

  async onActivate() {
    this.setupEventListeners();
    if (!this._eventSetup) {
      this._eventSetup = true;
    }
    if (!this._allSongs.length) {
      await this.loadSongs();
    }
  },

  setupEventListeners() {
    if (this._setup) return;
    this._setup = true;

    // Search
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
      searchInput.addEventListener('input', Utils.debounce(() => this.doSearch(), 250));
    }

    // Category filter
    const catFilter = document.getElementById('category-filter');
    if (catFilter) {
      catFilter.addEventListener('change', () => this.doSearch());
    }

    // New song button
    document.getElementById('btn-new-song')?.addEventListener('click', () => this.newSong());
    document.getElementById('btn-new-song-editor')?.addEventListener('click', () => this.newSong());

    // Save button
    document.getElementById('btn-save-song')?.addEventListener('click', () => {
      if (window.App) window.App.saveCurrentSong();
    });

    // Song editor
    const editor = document.getElementById('song-editor');
    if (editor) {
      editor.addEventListener('input', Utils.debounce(() => this.onEditorChange(), 300));
    }

    // Formatting toolbar
    document.getElementById('fmt-bold')?.addEventListener('click', () => this.toggleFormat('bold'));
    document.getElementById('fmt-italic')?.addEventListener('click', () => this.toggleFormat('italic'));
    document.getElementById('fmt-underline')?.addEventListener('click', () => this.toggleFormat('underline'));
    document.getElementById('fmt-strike')?.addEventListener('click', () => this.toggleFormat('strike'));
    document.getElementById('fmt-size')?.addEventListener('change', (e) => {
      document.execCommand('fontSize', false, e.target.value);
    });
    document.getElementById('fmt-color')?.addEventListener('input', (e) => {
      document.execCommand('foreColor', false, e.target.value);
    });
    document.getElementById('fmt-align-left')?.addEventListener('click', () => document.execCommand('justifyLeft'));
    document.getElementById('fmt-align-center')?.addEventListener('click', () => document.execCommand('justifyCenter'));
    document.getElementById('fmt-align-right')?.addEventListener('click', () => document.execCommand('justifyRight'));
  },

  async loadSongs() {
    appState.setLoading(true);
    try {
      const songs = await DB.songs.getAll(0, 500);
      this._allSongs = songs || [];
      this._filteredSongs = [...this._allSongs];
      this.renderSongList();
      this.updateCategoryFilter();
    } catch (e) {
      console.error('Load songs error:', e);
    }
    appState.setLoading(false);
  },

  renderSongList() {
    const el = document.getElementById('song-list');
    if (!el) return;
    const songs = this._filteredSongs;
    if (!songs.length) {
      el.innerHTML = '<div class="empty-state">Nu există cântări. Adaugă prima cântare!</div>';
      return;
    }
    el.innerHTML = songs.map(song => {
      const isCurrent = appState.get('currentSong') && appState.get('currentSong').id === song.id;
      const cat = song.category ? `<span class="category-badge">${Utils.escapeHtml(song.category)}</span>` : '';
      return `<div class="song-item ${isCurrent ? 'selected' : ''}" data-id="${song.id}">
        <div class="song-item-main">
          <span class="song-title">${Utils.escapeHtml(song.title)}</span>
          ${song.author ? `<span class="song-author">${Utils.escapeHtml(song.author)}</span>` : ''}
        </div>
        ${cat}
      </div>`;
    }).join('');

    el.querySelectorAll('.song-item').forEach(item => {
      item.addEventListener('click', () => {
        const id = parseInt(item.dataset.id);
        this.loadSong(id);
      });
      item.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        const id = parseInt(item.dataset.id);
        this.showContextMenu(e, id);
      });
    });
  },

  async loadSong(id) {
    try {
      const song = await DB.songs.getById(id);
      if (!song) return;
      appState.setCurrentSong(song);

      // Parse slides
      let slides = [];
      try { slides = JSON.parse(song.slides || '[]'); } catch {}
      if (!slides.length && song.lyrics) {
        slides = Utils.parseLyrics(song.lyrics);
      }
      appState.setSlides(slides);

      // Fill editor
      const editor = document.getElementById('song-editor');
      if (editor) {
        editor.value = slides.join('\n\n');
      }

      // Update song info bar
      document.getElementById('slide-counter').textContent = `${slides.length} slide-uri`;

      // Update word counter
      this.updateWordCounter();

      // Highlight in list
      document.querySelectorAll('.song-item').forEach(el => el.classList.remove('selected'));
      const sel = document.querySelector(`.song-item[data-id="${id}"]`);
      if (sel) sel.classList.add('selected');

    } catch (e) {
      console.error('Load song error:', e);
    }
  },

  doSearch() {
    const query = (document.getElementById('search-input')?.value || '').toLowerCase();
    const cat = document.getElementById('category-filter')?.value || '';

    this._filteredSongs = this._allSongs.filter(s => {
      if (query && !s.title.toLowerCase().includes(query) && !(s.author || '').toLowerCase().includes(query)) return false;
      if (cat && s.category !== cat) return false;
      return true;
    });
    this.renderSongList();
  },

  updateCategoryFilter() {
    const sel = document.getElementById('category-filter');
    if (!sel) return;
    const cats = [...new Set(this._allSongs.map(s => s.category).filter(Boolean))];
    sel.innerHTML = '<option value="">Toate categoriile</option>' +
      cats.map(c => `<option value="${Utils.escapeHtml(c)}">${Utils.escapeHtml(c)}</option>`).join('');
  },

  newSong() {
    const editor = document.getElementById('song-editor');
    if (editor) editor.value = '';
    appState.setCurrentSong({ title: '', author: '', category: '', lyrics: '', slides: '[]', id: null });
    appState.setSlides([]);
    document.getElementById('song-title')?.focus();
    document.getElementById('slide-counter').textContent = '0 slide-uri';
    this.updateWordCounter();
  },

  onEditorChange() {
    const editor = document.getElementById('song-editor');
    if (!editor) return;
    const text = editor.value;
    const slides = Utils.parseLyrics(text);
    appState.setSlides(slides);
    document.getElementById('slide-counter').textContent = `${slides.length} slide-uri`;
    this.updateWordCounter();
  },

  updateWordCounter() {
    const el = document.getElementById('word-counter');
    const editor = document.getElementById('song-editor');
    if (!el || !editor) return;
    const text = editor.value;
    const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
    const slides = text ? text.split(/\n\s*\n/).filter(b => b.trim()).length : 0;
    el.textContent = `${words} cuvinte | ${slides} slide-uri`;
  },

  showContextMenu(e, id) {
    const menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.style.cssText = `position:fixed;left:${e.clientX}px;top:${e.clientY}px;z-index:9999`;
    menu.innerHTML = `
      <div class="context-item" data-action="edit">✏ Editează</div>
      <div class="context-item" data-action="service">➕ Adaugă la serviciu</div>
      <div class="context-item" data-action="delete">🗑 Șterge</div>
      <div class="context-separator"></div>
      <div class="context-item" data-action="category">📁 Mută la categorie</div>
    `;
    document.body.appendChild(menu);

    const close = () => menu.remove();
    menu.addEventListener('click', async (ev) => {
      const item = ev.target.closest('.context-item');
      if (!item) return;
      const action = item.dataset.action;
      close();
      const song = await DB.songs.getById(id);
      if (!song) return;
      if (action === 'edit') {
        this.loadSong(id);
      } else if (action === 'service') {
        if (window.App) window.App.addToService(id, song.title);
      } else if (action === 'delete') {
        const ok = await Utils.confirm(`Ștergi "${song.title}"?`);
        if (ok) {
          await DB.songs.delete(id);
          this._allSongs = this._allSongs.filter(s => s.id !== id);
          this.doSearch();
          Utils.toast('Cântare ștearsă', 'info');
        }
      } else if (action === 'category') {
        const cat = await Utils.prompt('Categorie nouă:', '');
        if (cat !== null) {
          song.category = cat;
          await DB.songs.save(song);
          Utils.toast('Categorie actualizată', 'success');
        }
      }
    });

    document.addEventListener('click', close, { once: true });
  },

  toggleFormat(cmd) {
    document.execCommand(cmd, false, null);
    document.getElementById('song-editor')?.focus();
  },
};
