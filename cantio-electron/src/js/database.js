const DB = {
  _api: () => window.api.db,

  songs: {
    search: (q, p, l) => window.api.db.songs.search(q, p, l),
    getAll: (p, l) => window.api.db.songs.getAll(p, l),
    getById: (id) => window.api.db.songs.getById(id),
    save: (s) => window.api.db.songs.save(s),
    delete: (id) => window.api.db.songs.delete(id),
    getCategories: () => window.api.db.songs.getCategories(),
    getByCategory: (c, p, l) => window.api.db.songs.getByCategory(c, p, l),
    getCount: () => window.api.db.songs.getCount(),
    add: (t, c, s, a, cat, l) => window.api.db.songs.add(t, c, s, a, cat, l),
    countByCategory: () => window.api.db.songs.countByCategory(),
    exportJson: () => window.api.db.songs.exportJson(),
    importJson: (j) => window.api.db.songs.importJson(j),
  },

  bible: {
    search: (q, t) => window.api.db.bible.search(q, t),
    getBooks: (t) => window.api.db.bible.getBooks(t),
    getDefaultBooks: () => window.api.db.bible.getDefaultBooks(),
    getChapters: (b, t) => window.api.db.bible.getChapters(b, t),
    getVerses: (b, c, t) => window.api.db.bible.getVerses(b, c, t),
    getVerse: (b, c, v, t) => window.api.db.bible.getVerse(b, c, v, t),
    getTranslations: () => window.api.db.bible.getTranslations(),
    importData: (b, v, t) => window.api.db.bible.importData(b, v, t),
    initDefaultBooks: (t) => window.api.db.bible.initDefaultBooks(t),
  },

  playlists: {
    getAll: () => window.api.db.playlists.getAll(),
    getById: (id) => window.api.db.playlists.getById(id),
    save: (p) => window.api.db.playlists.save(p),
    delete: (id) => window.api.db.playlists.delete(id),
  },

  presentations: {
    getAll: () => window.api.db.presentations.getAll(),
    getById: (id) => window.api.db.presentations.getById(id),
    save: (p) => window.api.db.presentations.save(p),
    delete: (id) => window.api.db.presentations.delete(id),
  },

  profiles: {
    list: () => window.api.db.profiles.list(),
    load: (n) => window.api.db.profiles.load(n),
    create: (n) => window.api.db.profiles.create(n),
    delete: (n) => window.api.db.profiles.delete(n),
    rename: (o, n) => window.api.db.profiles.rename(o, n),
    setPassword: (n, p) => window.api.db.profiles.setPassword(n, p),
    checkPassword: (n, p) => window.api.db.profiles.checkPassword(n, p),
    setRestriction: (n, k, v) => window.api.db.profiles.setRestriction(n, k, v),
    getRestrictions: (n) => window.api.db.profiles.getRestrictions(n),
  },

  service: {
    getItems: (id) => window.api.db.service.getItems(id),
    saveItems: (id, items) => window.api.db.service.saveItems(id, items),
    clear: (id) => window.api.db.service.clear(id),
  },

  categories: {
    getAll: () => window.api.db.categories.getAll(),
    add: (n, c) => window.api.db.categories.add(n, c),
    delete: (n) => window.api.db.categories.delete(n),
  },

  cache: {
    get: (k) => window.api.db.cache.get(k),
    set: (k, v, t) => window.api.db.cache.set(k, v, t),
    delete: (k) => window.api.db.cache.delete(k),
  },

  checkIntegrity: () => window.api.db.checkIntegrity(),
  vacuum: () => window.api.db.vacuum(),
  reindex: () => window.api.db.reindex(),
};
