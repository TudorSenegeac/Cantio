const { contextBridge, ipcRenderer } = require('electron');

const validChannels = [
  'profile-loaded', 'display-closed', 'remote-started', 'remote-stopped',
  'remote-command', 'stage-data', 'shortcut-triggered',
  'media:videoStarted', 'media:videoStopped',
];

contextBridge.exposeInMainWorld('api', {
  // ═══════════════════════════════════════════════════════════════════════════
  // Database — Songs
  // ═══════════════════════════════════════════════════════════════════════════
  db: {
    songs: {
      search: (q, p, l) => ipcRenderer.invoke('db:songs:search', q, p, l),
      getAll: (p, l) => ipcRenderer.invoke('db:songs:getAll', p, l),
      getById: (id) => ipcRenderer.invoke('db:songs:getById', id),
      save: (s) => ipcRenderer.invoke('db:songs:save', s),
      delete: (id) => ipcRenderer.invoke('db:songs:delete', id),
      getCategories: () => ipcRenderer.invoke('db:songs:getCategories'),
      getByCategory: (c, p, l) => ipcRenderer.invoke('db:songs:getByCategory', c, p, l),
      getCount: () => ipcRenderer.invoke('db:songs:getCount'),
      add: (t, c, s, a, cat, l) => ipcRenderer.invoke('db:songs:add', t, c, s, a, cat, l),
      countByCategory: () => ipcRenderer.invoke('db:songs:countByCategory'),
      exportJson: () => ipcRenderer.invoke('db:songs:exportJson'),
      importJson: (j) => ipcRenderer.invoke('db:songs:importJson', j),
    },

    // ═════════════════════════════════════════════════════════════════════════
    // Database — Bible
    // ═════════════════════════════════════════════════════════════════════════
    bible: {
      search: (q, t) => ipcRenderer.invoke('db:bible:search', q, t),
      getBooks: (t) => ipcRenderer.invoke('db:bible:getBooks', t),
      getDefaultBooks: () => ipcRenderer.invoke('db:bible:getDefaultBooks'),
      getChapters: (b, t) => ipcRenderer.invoke('db:bible:getChapters', b, t),
      getVerses: (b, c, t) => ipcRenderer.invoke('db:bible:getVerses', b, c, t),
      getVerse: (b, c, v, t) => ipcRenderer.invoke('db:bible:getVerse', b, c, v, t),
      getTranslations: () => ipcRenderer.invoke('db:bible:getTranslations'),
      importData: (b, v, t) => ipcRenderer.invoke('db:bible:importData', b, v, t),
      initDefaultBooks: (t) => ipcRenderer.invoke('db:bible:initDefaultBooks', t),
    },

    // ═════════════════════════════════════════════════════════════════════════
    // Database — Playlists
    // ═════════════════════════════════════════════════════════════════════════
    playlists: {
      getAll: () => ipcRenderer.invoke('db:playlists:getAll'),
      getById: (id) => ipcRenderer.invoke('db:playlists:getById', id),
      save: (p) => ipcRenderer.invoke('db:playlists:save', p),
      delete: (id) => ipcRenderer.invoke('db:playlists:delete', id),
    },

    // ═════════════════════════════════════════════════════════════════════════
    // Database — Presentations
    // ═════════════════════════════════════════════════════════════════════════
    presentations: {
      getAll: () => ipcRenderer.invoke('db:presentations:getAll'),
      getById: (id) => ipcRenderer.invoke('db:presentations:getById', id),
      save: (p) => ipcRenderer.invoke('db:presentations:save', p),
      delete: (id) => ipcRenderer.invoke('db:presentations:delete', id),
    },

    // ═════════════════════════════════════════════════════════════════════════
    // Database — Profiles
    // ═════════════════════════════════════════════════════════════════════════
    profiles: {
      list: () => ipcRenderer.invoke('profiles:list'),
      load: (n) => ipcRenderer.invoke('profiles:load', n),
      create: (n) => ipcRenderer.invoke('profiles:create', n),
      delete: (n) => ipcRenderer.invoke('profiles:delete', n),
      rename: (o, n) => ipcRenderer.invoke('profiles:rename', o, n),
      setPassword: (n, p) => ipcRenderer.invoke('profiles:setPassword', n, p),
      checkPassword: (n, p) => ipcRenderer.invoke('profiles:checkPassword', n, p),
      setRestriction: (n, k, v) => ipcRenderer.invoke('profiles:setRestriction', n, k, v),
      getRestrictions: (n) => ipcRenderer.invoke('profiles:getRestrictions', n),
    },

    // ═════════════════════════════════════════════════════════════════════════
    // Database — Service
    // ═════════════════════════════════════════════════════════════════════════
    service: {
      getItems: (id) => ipcRenderer.invoke('db:service:getItems', id),
      saveItems: (id, items) => ipcRenderer.invoke('db:service:saveItems', id, items),
      clear: (id) => ipcRenderer.invoke('db:service:clear', id),
    },

    // ═════════════════════════════════════════════════════════════════════════
    // Database — Categories
    // ═════════════════════════════════════════════════════════════════════════
    categories: {
      getAll: () => ipcRenderer.invoke('db:categories:getAll'),
      add: (n, c) => ipcRenderer.invoke('db:categories:add', n, c),
      delete: (n) => ipcRenderer.invoke('db:categories:delete', n),
    },

    // ═════════════════════════════════════════════════════════════════════════
    // Database — Cache
    // ═════════════════════════════════════════════════════════════════════════
    cache: {
      get: (k) => ipcRenderer.invoke('db:cache:get', k),
      set: (k, v, t) => ipcRenderer.invoke('db:cache:set', k, v, t),
      delete: (k) => ipcRenderer.invoke('db:cache:delete', k),
    },

    // ═════════════════════════════════════════════════════════════════════════
    // Database — Maintenance
    // ═════════════════════════════════════════════════════════════════════════
    checkIntegrity: () => ipcRenderer.invoke('db:checkIntegrity'),
    vacuum: () => ipcRenderer.invoke('db:vacuum'),
    reindex: () => ipcRenderer.invoke('db:reindex'),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Settings
  // ═══════════════════════════════════════════════════════════════════════════
  settings: {
    get: () => ipcRenderer.invoke('settings:get'),
    set: (s) => ipcRenderer.invoke('settings:set', s),
    getAll: () => ipcRenderer.invoke('settings:getAll'),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Display
  // ═══════════════════════════════════════════════════════════════════════════
  display: {
    getScreens: () => ipcRenderer.invoke('display:getScreens'),
    show: (o) => ipcRenderer.invoke('display:show', o),
    black: (o) => ipcRenderer.invoke('display:black', o),
    ticker: (o) => ipcRenderer.invoke('display:ticker', o),
    hideTicker: () => ipcRenderer.invoke('display:hideTicker'),
    clock: (o) => ipcRenderer.invoke('display:clock', o),
    timer: (o) => ipcRenderer.invoke('display:timer', o),
    stopTimer: () => ipcRenderer.invoke('display:stopTimer'),
    logo: (o) => ipcRenderer.invoke('display:logo', o),
    hideLogo: () => ipcRenderer.invoke('display:hideLogo'),
    freeze: (o) => ipcRenderer.invoke('display:freeze', o),
    projectorOff: (o) => ipcRenderer.invoke('display:projectorOff', o),
    open: (o) => ipcRenderer.invoke('display:open', o),
    close: (o) => ipcRenderer.invoke('display:close', o),
    closeAll: () => ipcRenderer.invoke('display:closeAll'),
    clearText: (o) => ipcRenderer.invoke('display:clearText', o),
    setSettings: (o) => ipcRenderer.invoke('display:setSettings', o),
    getState: () => ipcRenderer.invoke('display:getState'),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Stage Monitor
  // ═══════════════════════════════════════════════════════════════════════════
  stage: {
    open: () => ipcRenderer.invoke('stage:open'),
    close: () => ipcRenderer.invoke('stage:close'),
    send: (d) => ipcRenderer.invoke('stage:send', d),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Remote Server
  // ═══════════════════════════════════════════════════════════════════════════
  remote: {
    start: (p) => ipcRenderer.invoke('remote:start', p),
    stop: () => ipcRenderer.invoke('remote:stop'),
    status: () => ipcRenderer.invoke('remote:status'),
    getUrl: () => ipcRenderer.invoke('remote:getUrl'),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Dialogs
  // ═══════════════════════════════════════════════════════════════════════════
  dialog: {
    openFile: (o) => ipcRenderer.invoke('dialog:openFile', o),
    saveFile: (o) => ipcRenderer.invoke('dialog:saveFile', o),
    openDirectory: () => ipcRenderer.invoke('dialog:openDirectory'),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Import
  // ═══════════════════════════════════════════════════════════════════════════
  importFile: (p) => ipcRenderer.invoke('import:file', p),
  importFolder: (p) => ipcRenderer.invoke('import:folder', p),

  // ═══════════════════════════════════════════════════════════════════════════
  // Online Songs
  // ═══════════════════════════════════════════════════════════════════════════
  onlineSongs: {
    search: (o) => ipcRenderer.invoke('online:search', o),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Translation
  // ═══════════════════════════════════════════════════════════════════════════
  translate: (o) => ipcRenderer.invoke('translate:text', o),

  // ═══════════════════════════════════════════════════════════════════════════
  // Service Files
  // ═══════════════════════════════════════════════════════════════════════════
  service: {
    save: (o) => ipcRenderer.invoke('service:save', o),
    load: (p) => ipcRenderer.invoke('service:load', p),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Export
  // ═══════════════════════════════════════════════════════════════════════════
  exportPdf: (o) => ipcRenderer.invoke('export:pdf', o),

  // ═══════════════════════════════════════════════════════════════════════════
  // Media
  // ═══════════════════════════════════════════════════════════════════════════
  media: {
    startVideo: (p) => ipcRenderer.invoke('media:startVideo', p),
    stopVideo: () => ipcRenderer.invoke('media:stopVideo'),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // System
  // ═══════════════════════════════════════════════════════════════════════════
  system: {
    getInfo: () => ipcRenderer.invoke('system:getInfo'),
    openFolder: (p) => ipcRenderer.invoke('system:openFolder', p),
    openExternal: (u) => ipcRenderer.invoke('system:openExternal', u),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Window Controls
  // ═══════════════════════════════════════════════════════════════════════════
  window: {
    minimize: () => ipcRenderer.invoke('window:minimize'),
    maximize: () => ipcRenderer.invoke('window:maximize'),
    close: () => ipcRenderer.invoke('window:close'),
    isMaximized: () => ipcRenderer.invoke('window:isMaximized'),
    setSize: (w, h) => ipcRenderer.invoke('window:setSize', w, h),
    fullscreen: (f) => ipcRenderer.invoke('window:fullscreen', f),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Keyboard Shortcuts
  // ═══════════════════════════════════════════════════════════════════════════
  shortcuts: {
    register: (o) => ipcRenderer.invoke('shortcuts:register', o),
    unregister: (a) => ipcRenderer.invoke('shortcuts:unregister', a),
    unregisterAll: () => ipcRenderer.invoke('shortcuts:unregisterAll'),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Themes
  // ═══════════════════════════════════════════════════════════════════════════
  themes: {
    getPath: () => ipcRenderer.invoke('themes:getPath'),
    list: () => ipcRenderer.invoke('themes:list'),
    save: (o) => ipcRenderer.invoke('themes:save', o),
    delete: (n) => ipcRenderer.invoke('themes:delete', n),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Cloud
  // ═══════════════════════════════════════════════════════════════════════════
  cloud: {
    upload: (o) => ipcRenderer.invoke('cloud:upload', o),
    download: (o) => ipcRenderer.invoke('cloud:download', o),
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Events from main process
  // ═══════════════════════════════════════════════════════════════════════════
  on: (channel, callback) => {
    if (validChannels.includes(channel)) {
      const sub = (_event, ...args) => callback(...args);
      ipcRenderer.on(channel, sub);
      return () => ipcRenderer.removeListener(channel, sub);
    }
  },
});
