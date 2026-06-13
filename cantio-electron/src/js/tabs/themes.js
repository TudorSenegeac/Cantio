Tabs = Tabs || {};
Tabs.themes = {
  _themes: [],

  async onActivate() {
    await this.loadThemes();
    this.setupEventListeners();
  },

  setupEventListeners() {
    if (this._setup) return;
    this._setup = true;

    document.getElementById('theme-grid')?.addEventListener('click', async (e) => {
      const card = e.target.closest('.theme-card');
      if (!card) return;
      const name = card.dataset.theme;
      if (e.target.closest('.theme-delete')) {
        const ok = await Utils.confirm(`Ștergi tema "${name}"?`);
        if (ok) {
          await window.api.themes.delete(name);
          await this.loadThemes();
        }
        return;
      }
      // Apply theme
      await this.applyTheme(name);
    });
  },

  async loadThemes() {
    try {
      this._themes = await window.api.themes.list();
      this.render();
    } catch (e) {
      console.error('Load themes error:', e);
    }
  },

  render() {
    const el = document.getElementById('theme-grid');
    if (!el) return;
    if (!this._themes.length) {
      el.innerHTML = '<div class="empty-state">Nu există teme. Creează una din setări.</div>';
      return;
    }
    el.innerHTML = this._themes.map(t => {
      const textColor = t.text_color || '#ffffff';
      const bgColor = t.bg_color || '#1e1e2e';
      return `<div class="theme-card" data-theme="${Utils.escapeHtml(t.name)}" style="background:${bgColor};color:${textColor}">
        <div class="theme-card-preview">
          <span style="font-size:24px;font-weight:bold">Aa</span>
          <span style="font-size:12px">${Utils.escapeHtml(t.name)}</span>
        </div>
        <div class="theme-card-footer">
          <span>${Utils.escapeHtml(t.name)}</span>
          <button class="btn-icon theme-delete" title="Șterge">✕</button>
        </div>
      </div>`;
    }).join('');
  },

  async applyTheme(name) {
    const theme = this._themes.find(t => t.name === name);
    if (!theme) return;
    await window.api.settings.set(theme);
    appState.setSettings(theme);
    Utils.toast(`Tema "${name}" aplicată`, 'success');
  },
};
