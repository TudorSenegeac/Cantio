Tabs = Tabs || {};
Tabs.slides = {
  onActivate() {
    this.render();
  },

  render() {
    const el = document.getElementById('slide-list');
    if (!el) return;
    const slides = appState.get('slides');
    const idx = appState.get('currentSlide');
    if (!slides || !slides.length) {
      el.innerHTML = '<div class="empty-state">Selectează sau creează o cântare cu slide-uri</div>';
      return;
    }
    el.innerHTML = slides.map((slide, i) => {
      const lines = slide.split('\n');
      const firstLines = lines.slice(0, 3).join('\n');
      const isActive = i === idx;
      return `<div class="slide-card ${isActive ? 'active' : ''}" data-index="${i}">
        <div class="slide-card-header">
          <span class="slide-label">${i + 1}</span>
          <div class="slide-card-actions">
            <button class="btn-icon slide-live" title="Trimite la live" data-index="${i}">▶</button>
            <button class="btn-icon slide-edit" title="Editează" data-index="${i}">✏</button>
            <button class="btn-icon slide-up" title="Sus" data-index="${i}">↑</button>
            <button class="btn-icon slide-down" title="Jos" data-index="${i}">↓</button>
            <button class="btn-icon slide-delete" title="Șterge" data-index="${i}">✕</button>
          </div>
        </div>
        <div class="slide-card-preview">${Utils.escapeHtml(firstLines)}</div>
      </div>`;
    }).join('');

    el.querySelectorAll('.slide-live').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const i = parseInt(e.target.closest('[data-index]').dataset.index);
        appState.setCurrentSlide(i);
        if (window.App) window.App.goLive();
      });
    });
    el.querySelectorAll('.slide-edit').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const i = parseInt(e.target.closest('[data-index]').dataset.index);
        const editor = document.getElementById('song-editor');
        if (editor) {
          const slides = appState.get('slides');
          editor.value = slides.join('\n\n');
          editor.focus();
          window.App.switchTab('songs');
        }
      });
    });
    el.querySelectorAll('.slide-up').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const i = parseInt(e.target.closest('[data-index]').dataset.index);
        this.reorderSlide(i, -1);
      });
    });
    el.querySelectorAll('.slide-down').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const i = parseInt(e.target.closest('[data-index]').dataset.index);
        this.reorderSlide(i, 1);
      });
    });
    el.querySelectorAll('.slide-delete').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const i = parseInt(e.target.closest('[data-index]').dataset.index);
        const ok = await Utils.confirm('Ștergi acest slide?');
        if (ok) this.deleteSlide(i);
      });
    });
  },

  reorderSlide(idx, direction) {
    const slides = [...appState.get('slides')];
    const newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= slides.length) return;
    [slides[idx], slides[newIdx]] = [slides[newIdx], slides[idx]];
    appState.set('slides', slides);
    appState.setCurrentSlide(newIdx);
    this.render();
    if (window.App) window.App.updateSlidePreview();
  },

  deleteSlide(idx) {
    let slides = [...appState.get('slides')];
    if (slides.length <= 1) { Utils.toast('Trebuie să rămână cel puțin un slide', 'warning'); return; }
    slides.splice(idx, 1);
    appState.set('slides', slides);
    const newIdx = Math.min(idx, slides.length - 1);
    appState.setCurrentSlide(newIdx);
    this.render();
    if (window.App) window.App.updateSlidePreview();
  },
};
