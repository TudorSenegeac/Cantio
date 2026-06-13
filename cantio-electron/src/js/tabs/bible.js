Tabs = Tabs || {};
Tabs.bible = {
  _books: [],
  _currentTranslation: 'niv',

  async onActivate() {
    this.setupEventListeners();
    if (!this._books.length) {
      await this.loadBooks();
    }
  },

  setupEventListeners() {
    if (this._setup) return;
    this._setup = true;

    const bookSel = document.getElementById('bible-book');
    const chapSel = document.getElementById('bible-chapter');
    const transSel = document.getElementById('bible-translation');
    const searchInput = document.getElementById('bible-search');

    bookSel?.addEventListener('change', () => this.loadChapters());
    chapSel?.addEventListener('change', () => this.loadVerses());
    transSel?.addEventListener('change', (e) => {
      this._currentTranslation = e.target.value;
      this.loadBooks();
    });
    searchInput?.addEventListener('input', Utils.debounce(() => this.doSearch(), 300));
  },

  async loadBooks() {
    try {
      const trans = this._currentTranslation;
      let books = await DB.bible.getBooks(trans);
      if (!books || !books.length) {
        books = await DB.bible.getDefaultBooks();
      }
      this._books = books || [];
      const sel = document.getElementById('bible-book');
      if (sel) {
        sel.innerHTML = this._books.map(b =>
          `<option value="${b.id}">${b.name}</option>`
        ).join('');
        this.loadChapters();
      }
      this.loadTranslations();
    } catch (e) {
      console.error('Load books error:', e);
    }
  },

  async loadTranslations() {
    try {
      const trans = await DB.bible.getTranslations();
      const sel = document.getElementById('bible-translation');
      if (sel && trans.length) {
        sel.innerHTML = trans.map(t =>
          `<option value="${t.code}" ${t.code === this._currentTranslation ? 'selected' : ''}>${t.name}</option>`
        ).join('');
      }
    } catch {}
  },

  async loadChapters() {
    const bookSel = document.getElementById('bible-book');
    if (!bookSel) return;
    const bookId = parseInt(bookSel.value);
    if (!bookId) return;
    try {
      const chapters = await DB.bible.getChapters(bookId, this._currentTranslation);
      const chapSel = document.getElementById('bible-chapter');
      if (chapSel) {
        chapSel.innerHTML = (chapters.length ? chapters : [1]).map(c =>
          `<option value="${c}">Capitolul ${c}</option>`
        ).join('');
        this.loadVerses();
      }
    } catch (e) {
      console.error('Load chapters error:', e);
    }
  },

  async loadVerses() {
    const bookSel = document.getElementById('bible-book');
    const chapSel = document.getElementById('bible-chapter');
    if (!bookSel || !chapSel) return;
    const bookId = parseInt(bookSel.value);
    const chapter = parseInt(chapSel.value);
    if (!bookId || !chapter) return;
    try {
      const verses = await DB.bible.getVerses(bookId, chapter, this._currentTranslation);
      this.renderVerses(verses || [], bookId, chapter);
    } catch (e) {
      console.error('Load verses error:', e);
    }
  },

  renderVerses(verses, bookId, chapter) {
    const el = document.getElementById('bible-verses');
    if (!el) return;
    if (!verses || !verses.length) {
      el.innerHTML = '<div class="empty-state">Niciun verset găsit</div>';
      return;
    }
    el.innerHTML = verses.map(v => {
      const ref = `${v.book_name || ''} ${chapter}:${v.verse}`;
      return `<div class="verse-item" data-book="${bookId}" data-chapter="${chapter}" data-verse="${v.verse}">
        <span class="verse-num">${v.verse}</span>
        <span class="verse-text">${Utils.escapeHtml(v.text)}</span>
        <span class="verse-actions">
          <button class="btn-icon verse-send" title="Trimite la live">▶</button>
          <button class="btn-icon verse-copy" title="Adaugă la slides">📋</button>
        </span>
      </div>`;
    }).join('');

    el.querySelectorAll('.verse-item').forEach(item => {
      item.addEventListener('dblclick', () => {
        const b = parseInt(item.dataset.book);
        const c = parseInt(item.dataset.chapter);
        const v = parseInt(item.dataset.verse);
        this.sendVerse(b, c, v);
      });
    });

    el.querySelectorAll('.verse-send').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const item = e.target.closest('.verse-item');
        const b = parseInt(item.dataset.book);
        const c = parseInt(item.dataset.chapter);
        const v = parseInt(item.dataset.verse);
        this.sendVerse(b, c, v);
      });
    });

    el.querySelectorAll('.verse-copy').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const item = e.target.closest('.verse-item');
        const text = item.querySelector('.verse-text')?.textContent || '';
        this.copyToSlides(text);
      });
    });
  },

  async sendVerse(bookId, chapter, verse) {
    try {
      const v = await DB.bible.getVerse(bookId, chapter, verse, this._currentTranslation);
      if (!v) return;
      const text = `${v.book_name || ''} ${chapter}:${verse}\n${v.text}`;
      if (window.App) {
        appState.setCurrentSong({ title: `${v.book_name} ${chapter}:${verse}`, author: '' });
        appState.setSlides([text]);
        window.App.goLive();
      }
    } catch (e) {
      console.error('Send verse error:', e);
    }
  },

  copyToSlides(text) {
    const editor = document.getElementById('song-editor');
    if (!editor) return;
    if (editor.value) editor.value += '\n\n';
    editor.value += text;
    if (window.App) {
      if (typeof Tabs.songs !== 'undefined' && Tabs.songs.onEditorChange) {
        Tabs.songs.onEditorChange();
      }
    }
  },

  async doSearch() {
    const input = document.getElementById('bible-search');
    const el = document.getElementById('bible-verses');
    if (!input || !el) return;
    const query = input.value.trim();
    if (!query) { this.loadVerses(); return; }
    try {
      const results = await DB.bible.search(query, this._currentTranslation);
      if (!results || !results.length) {
        el.innerHTML = '<div class="empty-state">Niciun rezultat</div>';
        return;
      }
      el.innerHTML = results.map(r =>
        `<div class="verse-item" data-book="${r.book_id}" data-chapter="${r.chapter}" data-verse="${r.verse}">
          <span class="verse-ref">${r.book_name} ${r.chapter}:${r.verse}</span>
          <span class="verse-text">${Utils.escapeHtml(r.text)}</span>
          <span class="verse-actions">
            <button class="btn-icon verse-send" title="Trimite la live">▶</button>
          </span>
        </div>`
      ).join('');
    } catch (e) {
      console.error('Bible search error:', e);
    }
  },
};
