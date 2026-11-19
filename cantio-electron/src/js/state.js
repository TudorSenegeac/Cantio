class AppState {
  constructor() {
    this._listeners = {};
    this._state = {
      profile: null,
      settings: {},
      currentTab: 'songs',
      currentSong: null,
      currentSlide: 0,
      slides: [],
      serviceItems: [],
      liveSlide: null,
      liveSong: null,
      displays: [],
      isLive: false,
      isFrozen: false,
      isProjectorOff: false,
      showLogo: false,
      showClock: false,
      showTimer: false,
      tickerText: '',
      autoAdvance: false,
      dualLanguage: false,
      translationText: '',
      remoteRunning: false,
      remoteUrl: null,
      searchQuery: '',
      songs: [],
      bibleBooks: [],
      bibleChapters: [],
      bibleVerses: [],
      selectedBook: null,
      selectedChapter: null,
      selectedVerse: null,
      bibleTranslation: 'niv',
      categories: [],
      playlists: [],
      presentations: [],
      themes: [],
      mediaFiles: [],
      onlineResults: [],
      importHistory: [],
      loading: false,
      modifiedSongs: [],
    };
  }

  get(key) { return this._state[key]; }
  set(key, value) {
    const old = this._state[key];
    this._state[key] = value;
    this._emit(key, value, old);
    if (key !== 'loading') this._emit('*', { key, value, old });
  }
  setAll(obj) { Object.entries(obj).forEach(([k, v]) => this.set(k, v)); }

  on(event, fn) {
    if (!this._listeners[event]) this._listeners[event] = [];
    this._listeners[event].push(fn);
    return () => { this._listeners[event] = this._listeners[event].filter(f => f !== fn); };
  }

  _emit(event, ...args) {
    (this._listeners[event] || []).forEach(fn => { try { fn(...args); } catch (e) { console.error('State listener error:', e); } });
  }

  watch(key, fn) {
    fn(this._state[key]);
    return this.on(key, fn);
  }

  // Convenience setters
  setProfile(profile) { this.set('profile', profile); }
  setSettings(settings) { this.set('settings', settings); }
  setTab(tab) { this.set('currentTab', tab); }
  setCurrentSong(song) { this.set('currentSong', song); }
  setSlides(slides) { this.set('slides', slides); this.set('currentSlide', 0); }
  setCurrentSlide(idx) { this.set('currentSlide', idx); }
  setLiveSlide(slide) { this.set('liveSlide', slide); }
  setLoading(v) { this.set('loading', v); }
  toggleLive() { this.set('isLive', !this._state.isLive); }
  toggleFreeze() { this.set('isFrozen', !this._state.isFrozen); }
  toggleProjector() { this.set('isProjectorOff', !this._state.isProjectorOff); }
  toggleLogo() { this.set('showLogo', !this._state.showLogo); }
  toggleClock() { this.set('showClock', !this._state.showClock); }
  toggleAutoAdvance() { this.set('autoAdvance', !this._state.autoAdvance); }
  toggleDualLanguage() { this.set('dualLanguage', !this._state.dualLanguage); }

  addToast(message, type = 'info') { Utils.toast(message, type); }
}

const appState = new AppState();
