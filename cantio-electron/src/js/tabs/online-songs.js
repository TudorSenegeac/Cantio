Tabs = Tabs || {};
Tabs.online = {
  onActivate() {
    this.setupEventListeners();
  },

  setupEventListeners() {
    if (this._setup) return;
    this._setup = true;

    document.getElementById('online-search-btn')?.addEventListener('click', () => this.search());
    document.getElementById('online-search')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.search();
    });
  },

  async search() {
    const query = document.getElementById('online-search')?.value?.trim();
    if (!query) { Utils.toast('Introdu un termen de căutare', 'warning'); return; }
    const source = document.getElementById('online-source')?.value || 'cantaricrestine';

    appState.setLoading(true);
    try {
      const results = await window.api.onlineSongs.search({ query, source });
      this.renderResults(results);
    } catch (e) {
      Utils.toast('Eroare căutare: ' + e.message, 'error');
    }
    appState.setLoading(false);
  },

  renderResults(results) {
    const el = document.getElementById('online-results');
    if (!el) return;
    if (!results || results.length === 0) {
      el.innerHTML = '<div class="empty-state">Niciun rezultat</div>';
      return;
    }
    el.innerHTML = results.map((r, i) =>
      `<div class="song-item online-result" data-index="${i}">
        <div class="song-item-main">
          <span class="song-title">${Utils.escapeHtml(r.title || r.name || '')}</span>
          ${r.author ? `<span class="song-author">${Utils.escapeHtml(r.author)}</span>` : ''}
        </div>
        <div class="online-actions">
          <button class="btn btn-sm btn-primary online-send" data-index="${i}">▶ Trimite</button>
          <button class="btn btn-sm btn-secondary online-import" data-index="${i}">📥 Importă</button>
        </div>
      </div>`
    ).join('');

    el.querySelectorAll('.online-send').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const i = parseInt(e.target.closest('[data-index]').dataset.index);
        const song = results[i];
        if (song && window.App) {
          const slides = song.slides || Utils.parseLyrics(song.content || song.lyrics || '');
          appState.setCurrentSong({ title: song.title, author: song.author || '' });
          appState.setSlides(slides);
          window.App.goLive();
        }
      });
    });

    el.querySelectorAll('.online-import').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const i = parseInt(e.target.closest('[data-index]').dataset.index);
        const song = results[i];
        if (!song) return;
        try {
          const slides = song.slides || Utils.parseLyrics(song.content || song.lyrics || '');
          const id = await DB.songs.add(
            song.title || song.name || '',
            song.content || song.lyrics || '',
            slides,
            song.author || '',
            'General',
            'ro'
          );
          if (id) Utils.toast(`"${song.title}" importată`, 'success');
        } catch (e) {
          Utils.toast('Eroare import: ' + e.message, 'error');
        }
      });
    });
  },
};
