Tabs = Tabs || {};
Tabs.overlays = {
  onActivate() {
    this.setupEventListeners();
  },

  setupEventListeners() {
    if (this._setup) return;
    this._setup = true;

    document.getElementById('overlay-ticker-send')?.addEventListener('click', () => {
      const text = document.getElementById('overlay-ticker')?.value || '';
      if (text) {
        window.api.display.ticker({ text, speed: 2.5, color: '#f9e2af' });
        appState.set('tickerText', text);
        Utils.toast('Ticker trimis', 'success');
      }
    });

    document.getElementById('overlay-timer-start')?.addEventListener('click', () => {
      const sec = parseInt(document.getElementById('overlay-timer')?.value || '60');
      window.api.display.timer({ seconds: sec, color: '#a6e3a1' });
      appState.set('showTimer', true);
    });

    document.getElementById('overlay-copyright')?.addEventListener('input', Utils.debounce((e) => {
      const text = e.target.value;
      const settings = appState.get('settings');
      settings.copyright = JSON.stringify({ enabled: !!text, mode: 'custom', custom_text: text, position: 'bottom_right', color: '#ffffff', opacity: 0.4, font_size: 12 });
      window.api.settings.set(settings);
    }, 500));
  },
};
