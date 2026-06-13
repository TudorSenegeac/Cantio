const path = require('path');
const fs = require('fs');
let initSqlJs;
try { initSqlJs = require('sql.js'); } catch { initSqlJs = null; }

const BIBLE_BOOKS_RO = [
  {id:1,name:'Geneza',abbreviation:'Gen'},{id:2,name:'Exodul',abbreviation:'Ex'},
  {id:3,name:'Leviticul',abbreviation:'Lev'},{id:4,name:'Numeri',abbreviation:'Num'},
  {id:5,name:'Deuteronomul',abbreviation:'Deut'},{id:6,name:'Iosua',abbreviation:'Ios'},
  {id:7,name:'Judecătorii',abbreviation:'Jud'},{id:8,name:'Rut',abbreviation:'Rut'},
  {id:9,name:'1 Samuel',abbreviation:'1Sam'},{id:10,name:'2 Samuel',abbreviation:'2Sam'},
  {id:11,name:'1 Regi',abbreviation:'1Reg'},{id:12,name:'2 Regi',abbreviation:'2Reg'},
  {id:13,name:'1 Cronici',abbreviation:'1Cron'},{id:14,name:'2 Cronici',abbreviation:'2Cron'},
  {id:15,name:'Ezra',abbreviation:'Ezra'},{id:16,name:'Neemia',abbreviation:'Neem'},
  {id:17,name:'Estera',abbreviation:'Est'},{id:18,name:'Iov',abbreviation:'Iov'},
  {id:19,name:'Psalmi',abbreviation:'Ps'},{id:20,name:'Proverbe',abbreviation:'Prov'},
  {id:21,name:'Eclesiastul',abbreviation:'Ecl'},{id:22,name:'Cântarea Cântărilor',abbreviation:'CC'},
  {id:23,name:'Isaia',abbreviation:'Is'},{id:24,name:'Ieremia',abbreviation:'Ier'},
  {id:25,name:'Plângerile',abbreviation:'Pl'},{id:26,name:'Ezechiel',abbreviation:'Ez'},
  {id:27,name:'Daniel',abbreviation:'Dan'},{id:28,name:'Osea',abbreviation:'Os'},
  {id:29,name:'Ioel',abbreviation:'Ioel'},{id:30,name:'Amos',abbreviation:'Am'},
  {id:31,name:'Obadia',abbreviation:'Obad'},{id:32,name:'Iona',abbreviation:'Iona'},
  {id:33,name:'Mica',abbreviation:'Mica'},{id:34,name:'Naum',abbreviation:'Naum'},
  {id:35,name:'Habacuc',abbreviation:'Hab'},{id:36,name:'Țefania',abbreviation:'Țef'},
  {id:37,name:'Hagai',abbreviation:'Hag'},{id:38,name:'Zaharia',abbreviation:'Zah'},
  {id:39,name:'Maleahi',abbreviation:'Mal'},
  {id:40,name:'Matei',abbreviation:'Mat'},{id:41,name:'Marcu',abbreviation:'Mc'},
  {id:42,name:'Luca',abbreviation:'Lc'},{id:43,name:'Ioan',abbreviation:'In'},
  {id:44,name:'Faptele Apostolilor',abbreviation:'FA'},{id:45,name:'Romani',abbreviation:'Rom'},
  {id:46,name:'1 Corinteni',abbreviation:'1Cor'},{id:47,name:'2 Corinteni',abbreviation:'2Cor'},
  {id:48,name:'Galateni',abbreviation:'Gal'},{id:49,name:'Efeseni',abbreviation:'Ef'},
  {id:50,name:'Filipeni',abbreviation:'Fil'},{id:51,name:'Coloseni',abbreviation:'Col'},
  {id:52,name:'1 Tesaloniceni',abbreviation:'1Tes'},{id:53,name:'2 Tesaloniceni',abbreviation:'2Tes'},
  {id:54,name:'1 Timotei',abbreviation:'1Tim'},{id:55,name:'2 Timotei',abbreviation:'2Tim'},
  {id:56,name:'Tit',abbreviation:'Tit'},{id:57,name:'Filimon',abbreviation:'Filim'},
  {id:58,name:'Evrei',abbreviation:'Evr'},{id:59,name:'Iacov',abbreviation:'Iac'},
  {id:60,name:'1 Petru',abbreviation:'1Pet'},{id:61,name:'2 Petru',abbreviation:'2Pet'},
  {id:62,name:'1 Ioan',abbreviation:'1In'},{id:63,name:'2 Ioan',abbreviation:'2In'},
  {id:64,name:'3 Ioan',abbreviation:'3In'},{id:65,name:'Iuda',abbreviation:'Iuda'},
  {id:66,name:'Apocalipsa',abbreviation:'Apoc'},
];

class Database {
  constructor(profileDir) {
    this.profileDir = profileDir;
    this.ready = false;
    this.songsDb = null;
    this.bibleDb = null;
    this._initPromise = this.init();
  }

  async init() {
    if (!initSqlJs) return;
    const SQL = await initSqlJs();
    fs.mkdirSync(this.profileDir, { recursive: true });

    const songsPath = path.join(this.profileDir, 'songs.db');
    const biblePath = path.join(this.profileDir, 'bible.db');

    if (fs.existsSync(songsPath)) {
      this.songsDb = new SQL.Database(fs.readFileSync(songsPath));
    } else {
      this.songsDb = new SQL.Database();
    }

    if (fs.existsSync(biblePath)) {
      this.bibleDb = new SQL.Database(fs.readFileSync(biblePath));
    } else {
      this.bibleDb = new SQL.Database();
    }

    this._migrateSongs();
    this._migrateBible();
    this._saveSongs();
    this._saveBible();
    this.ready = true;
  }

  _saveSongs() { if (this.songsDb) fs.writeFileSync(path.join(this.profileDir, 'songs.db'), this.songsDb.export()); }
  _saveBible() { if (this.bibleDb) fs.writeFileSync(path.join(this.profileDir, 'bible.db'), this.bibleDb.export()); }

  _save(db) {
    if (db === this.songsDb) this._saveSongs();
    else this._saveBible();
  }

  async _awaitReady() {
    if (this.ready) return;
    await this._initPromise;
  }

  _all(db, sql, params = []) {
    const stmt = db.prepare(sql);
    if (params.length > 0) stmt.bind(params);
    const results = [];
    while (stmt.step()) results.push(stmt.getAsObject());
    stmt.free();
    return results;
  }

  _get(db, sql, params = []) {
    const rows = this._all(db, sql, params);
    return rows.length > 0 ? rows[0] : null;
  }

  _run(db, sql, params = []) {
    db.run(sql, params);
    this._save(db);
  }

  _runInsert(db, sql, params = []) {
    db.run(sql, params);
    const rows = db.exec('SELECT last_insert_rowid() as id');
    this._save(db);
    return rows && rows[0] && rows[0].values ? Number(rows[0].values[0][0]) : null;
  }

  _exec(db, sql) {
    db.exec(sql);
  }

  _migrateSongs() {
    if (!this.songsDb) return;
    this._exec(this.songsDb, `CREATE TABLE IF NOT EXISTS songs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      author TEXT DEFAULT '',
      category TEXT DEFAULT '',
      language TEXT DEFAULT 'ro',
      lyrics TEXT DEFAULT '',
      slides TEXT DEFAULT '',
      copyright TEXT DEFAULT '',
      ccli TEXT DEFAULT '',
      key TEXT DEFAULT '',
      tempo TEXT DEFAULT '',
      notes TEXT DEFAULT '',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);
    this._exec(this.songsDb, `CREATE TABLE IF NOT EXISTS playlists (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      items TEXT DEFAULT '[]',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);
    this._exec(this.songsDb, `CREATE TABLE IF NOT EXISTS presentations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      data TEXT DEFAULT '{}',
      slides TEXT DEFAULT '[]',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);
    this._exec(this.songsDb, `CREATE TABLE IF NOT EXISTS categories (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT UNIQUE NOT NULL,
      color TEXT DEFAULT '#5294e2',
      sort_order INTEGER DEFAULT 0
    )`);
    this._exec(this.songsDb, `CREATE TABLE IF NOT EXISTS service_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      service_id TEXT NOT NULL,
      sort_order INTEGER DEFAULT 0,
      item_type TEXT DEFAULT 'song',
      item_id INTEGER DEFAULT NULL,
      title TEXT DEFAULT '',
      notes TEXT DEFAULT '',
      theme TEXT DEFAULT '',
      duration_seconds INTEGER DEFAULT 0
    )`);
    this._exec(this.songsDb, `CREATE TABLE IF NOT EXISTS cache (
      key TEXT PRIMARY KEY,
      value TEXT,
      expires_at DATETIME
    )`);

    try { this._exec(this.songsDb, 'CREATE VIRTUAL TABLE IF NOT EXISTS songs_fts USING fts5(title, author, lyrics, content=songs, content_rowid=id)'); } catch {}
    try { this._exec(this.songsDb, `INSERT INTO songs_fts(songs_fts) VALUES('rebuild')`); } catch {}
  }

  _migrateBible() {
    if (!this.bibleDb) return;
    this._exec(this.bibleDb, `CREATE TABLE IF NOT EXISTS books (
      id INTEGER PRIMARY KEY, name TEXT NOT NULL,
      abbreviation TEXT, testament TEXT DEFAULT 'OT'
    )`);
    this._exec(this.bibleDb, `CREATE TABLE IF NOT EXISTS verses (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      book_id INTEGER NOT NULL, chapter INTEGER NOT NULL,
      verse INTEGER NOT NULL, text TEXT NOT NULL,
      translation TEXT DEFAULT 'niv',
      FOREIGN KEY (book_id) REFERENCES books(id)
    )`);
    this._exec(this.bibleDb, `CREATE TABLE IF NOT EXISTS translations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
      language TEXT DEFAULT 'ro'
    )`);
    this._exec(this.bibleDb, 'CREATE INDEX IF NOT EXISTS idx_verses_ref ON verses(book_id, chapter, verse)');
    this._exec(this.bibleDb, 'CREATE INDEX IF NOT EXISTS idx_verses_trans ON verses(translation)');
    try { this._exec(this.bibleDb, 'CREATE VIRTUAL TABLE IF NOT EXISTS verses_fts USING fts5(text, content=verses, content_rowid=id)'); } catch {}
    try { this._exec(this.bibleDb, `INSERT INTO verses_fts(verses_fts) VALUES('rebuild')`); } catch {}
  }

  // ═════════════════════════════════════════════════════════════════════════════
  // SONGS
  // ═════════════════════════════════════════════════════════════════════════════

  async searchSongs(query, page = 0, limit = 200) {
    await this._awaitReady(); if (!this.songsDb) return [];
    const offset = page * limit;
    try {
      const q = query.replace(/[%_]/g, '\\$&');
      return this._all(this.songsDb,
        'SELECT s.* FROM songs s LEFT JOIN songs_fts f ON s.id = f.rowid WHERE songs_fts MATCH ? ORDER BY rank LIMIT ? OFFSET ?',
        [q, limit, offset]);
    } catch {
      const q = `%${query}%`;
      return this._all(this.songsDb,
        'SELECT * FROM songs WHERE title LIKE ? OR author LIKE ? OR lyrics LIKE ? ORDER BY title LIMIT ? OFFSET ?',
        [q, q, q, limit, offset]);
    }
  }

  async getAllSongs(page = 0, limit = 500) {
    await this._awaitReady(); if (!this.songsDb) return [];
    return this._all(this.songsDb, 'SELECT * FROM songs ORDER BY title LIMIT ? OFFSET ?', [limit, page * limit]);
  }

  async getSongById(id) {
    await this._awaitReady(); if (!this.songsDb) return null;
    return this._get(this.songsDb, 'SELECT * FROM songs WHERE id = ?', [id]);
  }

  async getCategories() {
    await this._awaitReady(); if (!this.songsDb) return [];
    return this._all(this.songsDb, 'SELECT DISTINCT category FROM songs WHERE category != "" ORDER BY category').map(r => r.category);
  }

  async getSongsByCategory(category, page = 0, limit = 200) {
    await this._awaitReady(); if (!this.songsDb) return [];
    return this._all(this.songsDb, 'SELECT * FROM songs WHERE category = ? ORDER BY title LIMIT ? OFFSET ?', [category, limit, page * limit]);
  }

  async saveSong(song) {
    await this._awaitReady(); if (!this.songsDb) return null;
    const slides = song.slides || '';
    const lyrics = song.lyrics || '';
    if (song.id) {
      this._run(this.songsDb,
        'UPDATE songs SET title=?, author=?, category=?, language=?, lyrics=?, slides=?, copyright=?, ccli=?, key=?, tempo=?, notes=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
        [song.title, song.author||'', song.category||'', song.language||'ro', lyrics, slides, song.copyright||'', song.ccli||'', song.key||'', song.tempo||'', song.notes||'', song.id]);
      this._syncFtsSong(song.id);
      return song.id;
    } else {
      const id = this._runInsert(this.songsDb,
        'INSERT INTO songs (title, author, category, language, lyrics, slides, copyright, ccli, key, tempo, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        [song.title, song.author||'', song.category||'', song.language||'ro', lyrics, slides, song.copyright||'', song.ccli||'', song.key||'', song.tempo||'', song.notes||'']);
      if (id) this._syncFtsSong(id);
      return id;
    }
  }

  async deleteSong(id) {
    await this._awaitReady(); if (!this.songsDb) return;
    this._run(this.songsDb, 'DELETE FROM songs WHERE id = ?', [id]);
    try { this._run(this.songsDb, 'DELETE FROM songs_fts WHERE rowid = ?', [id]); } catch {}
  }

  _syncFtsSong(id) {
    try {
      const song = this._get(this.songsDb, 'SELECT title, author, lyrics FROM songs WHERE id = ?', [id]);
      if (song) {
        this._run(this.songsDb, 'INSERT INTO songs_fts(rowid, title, author, lyrics) VALUES (?, ?, ?, ?)',
          [id, song.title, song.author||'', song.lyrics||'']);
      }
    } catch {}
  }

  async getSongCount() {
    await this._awaitReady(); if (!this.songsDb) return 0;
    const r = this._get(this.songsDb, 'SELECT COUNT(*) as cnt FROM songs');
    return r ? r.cnt : 0;
  }

  async addSong(title, content, slides, author, category, language) {
    await this._awaitReady();
    const check = this._get(this.songsDb, 'SELECT id FROM songs WHERE title = ? AND author = ?', [title, author||'']);
    if (check) return check.id;
    const id = this._runInsert(this.songsDb,
      'INSERT INTO songs (title, author, category, language, lyrics, slides) VALUES (?, ?, ?, ?, ?, ?)',
      [title, author||'', category||'General', language||'ro', content||'', JSON.stringify(slides||[])]);
    if (id) this._syncFtsSong(id);
    return id;
  }

  // ═════════════════════════════════════════════════════════════════════════════
  // PLAYLISTS
  // ═════════════════════════════════════════════════════════════════════════════

  async getAllPlaylists() {
    await this._awaitReady(); if (!this.songsDb) return [];
    const rows = this._all(this.songsDb, 'SELECT * FROM playlists ORDER BY name');
    return rows.map(r => ({ ...r, items: JSON.parse(r.items || '[]') }));
  }

  async getPlaylistById(id) {
    await this._awaitReady(); if (!this.songsDb) return null;
    const r = this._get(this.songsDb, 'SELECT * FROM playlists WHERE id = ?', [id]);
    if (!r) return null;
    return { ...r, items: JSON.parse(r.items || '[]') };
  }

  async savePlaylist(playlist) {
    await this._awaitReady(); if (!this.songsDb) return null;
    const items = JSON.stringify(playlist.items || []);
    if (playlist.id) {
      this._run(this.songsDb, 'UPDATE playlists SET name=?, items=? WHERE id=?', [playlist.name, items, playlist.id]);
      return playlist.id;
    } else {
      return this._runInsert(this.songsDb, 'INSERT INTO playlists (name, items) VALUES (?, ?)', [playlist.name, items]);
    }
  }

  async deletePlaylist(id) {
    await this._awaitReady(); if (!this.songsDb) return;
    this._run(this.songsDb, 'DELETE FROM playlists WHERE id = ?', [id]);
  }

  // ═════════════════════════════════════════════════════════════════════════════
  // PRESENTATIONS
  // ═════════════════════════════════════════════════════════════════════════════

  async getAllPresentations() {
    await this._awaitReady(); if (!this.songsDb) return [];
    return this._all(this.songsDb, 'SELECT id, title, created_at, updated_at FROM presentations ORDER BY title');
  }

  async getPresentation(id) {
    await this._awaitReady(); if (!this.songsDb) return null;
    const r = this._get(this.songsDb, 'SELECT * FROM presentations WHERE id = ?', [id]);
    if (!r) return null;
    try { r.slides = JSON.parse(r.slides || '[]'); } catch { r.slides = []; }
    try { r.data = JSON.parse(r.data || '{}'); } catch { r.data = {}; }
    return r;
  }

  async savePresentation(pres) {
    await this._awaitReady(); if (!this.songsDb) return null;
    const slides = JSON.stringify(pres.slides || []);
    const data = JSON.stringify(pres.data || {});
    if (pres.id) {
      this._run(this.songsDb, 'UPDATE presentations SET title=?, slides=?, data=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
        [pres.title, slides, data, pres.id]);
      return pres.id;
    } else {
      return this._runInsert(this.songsDb, 'INSERT INTO presentations (title, slides, data) VALUES (?, ?, ?)',
        [pres.title, slides, data]);
    }
  }

  async deletePresentation(id) {
    await this._awaitReady(); if (!this.songsDb) return;
    this._run(this.songsDb, 'DELETE FROM presentations WHERE id = ?', [id]);
  }

  // ═════════════════════════════════════════════════════════════════════════════
  // SERVICE ITEMS
  // ═════════════════════════════════════════════════════════════════════════════

  async getServiceItems(serviceId) {
    await this._awaitReady(); if (!this.songsDb) return [];
    return this._all(this.songsDb, 'SELECT * FROM service_items WHERE service_id = ? ORDER BY sort_order', [serviceId]);
  }

  async saveServiceItems(serviceId, items) {
    await this._awaitReady(); if (!this.songsDb) return;
    this._run(this.songsDb, 'DELETE FROM service_items WHERE service_id = ?', [serviceId]);
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      this._run(this.songsDb,
        'INSERT INTO service_items (service_id, sort_order, item_type, item_id, title, notes, theme, duration_seconds) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        [serviceId, i, item.item_type||'song', item.item_id||null, item.title||'', item.notes||'', item.theme||'', item.duration_seconds||0]);
    }
  }

  async clearService(serviceId) {
    await this._awaitReady(); if (!this.songsDb) return;
    this._run(this.songsDb, 'DELETE FROM service_items WHERE service_id = ?', [serviceId]);
  }

  // ═════════════════════════════════════════════════════════════════════════════
  // CACHE
  // ═════════════════════════════════════════════════════════════════════════════

  async cacheGet(key) {
    await this._awaitReady(); if (!this.songsDb) return null;
    const r = this._get(this.songsDb, 'SELECT value FROM cache WHERE key = ? AND (expires_at IS NULL OR expires_at > datetime("now"))', [key]);
    return r ? r.value : null;
  }

  async cacheSet(key, value, ttlHours = 24) {
    await this._awaitReady(); if (!this.songsDb) return;
    this._run(this.songsDb,
      'INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, datetime("now", ?))',
      [key, value, `+${ttlHours} hours`]);
  }

  async cacheDelete(key) {
    await this._awaitReady(); if (!this.songsDb) return;
    this._run(this.songsDb, 'DELETE FROM cache WHERE key = ?', [key]);
  }

  // ═════════════════════════════════════════════════════════════════════════════
  // BIBLE
  // ═════════════════════════════════════════════════════════════════════════════

  async searchBible(query, translation) {
    await this._awaitReady(); if (!this.bibleDb) return [];
    const q = `%${query}%`;
    const trans = translation || 'niv';
    return this._all(this.bibleDb,
      'SELECT v.*, b.name as book_name, b.abbreviation FROM verses v JOIN books b ON v.book_id = b.id WHERE v.text LIKE ? AND v.translation = ? ORDER BY v.book_id, v.chapter, v.verse LIMIT 100',
      [q, trans]);
  }

  async getBibleBooks(translation) {
    await this._awaitReady(); if (!this.bibleDb) return [];
    const trans = translation || 'niv';
    return this._all(this.bibleDb, 'SELECT DISTINCT b.* FROM books b JOIN verses v ON b.id = v.book_id WHERE v.translation = ? ORDER BY b.id', [trans]);
  }

  async getBibleChapters(book, translation) {
    await this._awaitReady(); if (!this.bibleDb) return [];
    const trans = translation || 'niv';
    return this._all(this.bibleDb, 'SELECT DISTINCT chapter FROM verses WHERE book_id = ? AND translation = ? ORDER BY chapter', [book, trans]).map(r => r.chapter);
  }

  async getBibleVerses(book, chapter, translation) {
    await this._awaitReady(); if (!this.bibleDb) return [];
    const trans = translation || 'niv';
    return this._all(this.bibleDb,
      'SELECT v.*, b.name as book_name, b.abbreviation FROM verses v JOIN books b ON v.book_id = b.id WHERE v.book_id = ? AND v.chapter = ? AND v.translation = ? ORDER BY v.verse',
      [book, chapter, trans]);
  }

  async getBibleVerse(book, chapter, verse, translation) {
    await this._awaitReady(); if (!this.bibleDb) return null;
    const trans = translation || 'niv';
    return this._get(this.bibleDb,
      'SELECT v.*, b.name as book_name, b.abbreviation FROM verses v JOIN books b ON v.book_id = b.id WHERE v.book_id = ? AND v.chapter = ? AND v.verse = ? AND v.translation = ?',
      [book, chapter, verse, trans]);
  }

  async getBibleTranslations() {
    await this._awaitReady(); if (!this.bibleDb) return [];
    return this._all(this.bibleDb, 'SELECT * FROM translations');
  }

  async importBibleData(books, verses, translation) {
    await this._awaitReady(); if (!this.bibleDb) return;
    const trans = translation || 'niv';
    const existingTrans = this._get(this.bibleDb, 'SELECT id FROM translations WHERE code = ?', [trans]);
    if (!existingTrans) {
      this._run(this.bibleDb, 'INSERT INTO translations (code, name, language) VALUES (?, ?, ?)',
        [trans, trans.toUpperCase(), 'ro']);
    }
    for (const book of books) {
      const existing = this._get(this.bibleDb, 'SELECT id FROM books WHERE id = ?', [book.id]);
      if (!existing) {
        this._run(this.bibleDb, 'INSERT INTO books (id, name, abbreviation, testament) VALUES (?, ?, ?, ?)',
          [book.id, book.name, book.abbreviation, book.testament||'OT']);
      }
    }
    for (const verse of verses) {
      this._run(this.bibleDb,
        'INSERT OR IGNORE INTO verses (book_id, chapter, verse, text, translation) VALUES (?, ?, ?, ?, ?)',
        [verse.book_id, verse.chapter, verse.verse, verse.text, trans]);
    }
  }

  async initDefaultBibleBooks(translation) {
    await this._awaitReady(); if (!this.bibleDb) return;
    const trans = translation || 'niv';
    const existingTrans = this._get(this.bibleDb, 'SELECT id FROM translations WHERE code = ?', [trans]);
    if (!existingTrans) {
      this._run(this.bibleDb, 'INSERT INTO translations (code, name, language) VALUES (?, ?, ?)',
        [trans, trans.toUpperCase(), 'ro']);
    }
    for (const book of BIBLE_BOOKS_RO) {
      const existing = this._get(this.bibleDb, 'SELECT id FROM books WHERE id = ?', [book.id]);
      if (!existing) {
        const testament = book.id <= 39 ? 'OT' : 'NT';
        this._run(this.bibleDb, 'INSERT INTO books (id, name, abbreviation, testament) VALUES (?, ?, ?, ?)',
          [book.id, book.name, book.abbreviation, testament]);
      }
    }
  }

  async getDefaultBibleBooks() {
    await this._awaitReady();
    return BIBLE_BOOKS_RO;
  }

  // ═════════════════════════════════════════════════════════════════════════════
  // CATEGORIES
  // ═════════════════════════════════════════════════════════════════════════════

  async getAllCategories() {
    await this._awaitReady(); if (!this.songsDb) return [];
    return this._all(this.songsDb, 'SELECT * FROM categories ORDER BY sort_order, name');
  }

  async addCategory(name, color) {
    await this._awaitReady(); if (!this.songsDb) return null;
    return this._runInsert(this.songsDb, 'INSERT OR IGNORE INTO categories (name, color) VALUES (?, ?)', [name, color||'#5294e2']);
  }

  async deleteCategory(name) {
    await this._awaitReady(); if (!this.songsDb) return;
    this._run(this.songsDb, 'DELETE FROM categories WHERE name = ?', [name]);
    this._run(this.songsDb, 'UPDATE songs SET category = "" WHERE category = ?', [name]);
  }

  // ═════════════════════════════════════════════════════════════════════════════
  // INTEGRITY & EXPORT
  // ═════════════════════════════════════════════════════════════════════════════

  async checkIntegrity() {
    await this._awaitReady();
    const results = {};
    if (this.songsDb) {
      try {
        const r = this._get(this.songsDb, 'PRAGMA integrity_check');
        results.songs = r ? r['integrity_check'] : 'ok';
      } catch { results.songs = 'error'; }
    }
    if (this.bibleDb) {
      try {
        const r = this._get(this.bibleDb, 'PRAGMA integrity_check');
        results.bible = r ? r['integrity_check'] : 'ok';
      } catch { results.bible = 'error'; }
    }
    return results;
  }

  async exportSongsJson() {
    await this._awaitReady(); if (!this.songsDb) return '[]';
    const songs = this._all(this.songsDb, 'SELECT * FROM songs ORDER BY id');
    return JSON.stringify(songs, null, 2);
  }

  async importSongsJson(jsonStr) {
    await this._awaitReady(); if (!this.songsDb) return 0;
    const songs = JSON.parse(jsonStr);
    let count = 0;
    for (const song of songs) {
      this._run(this.songsDb,
        'INSERT OR REPLACE INTO songs (id, title, author, category, language, lyrics, slides, copyright, ccli, key, tempo, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        [song.id, song.title, song.author||'', song.category||'', song.language||'ro', song.lyrics||'', song.slides||'', song.copyright||'', song.ccli||'', song.key||'', song.tempo||'', song.notes||'']);
      this._syncFtsSong(song.id);
      count++;
    }
    return count;
  }

  async getSongCountByCategory() {
    await this._awaitReady(); if (!this.songsDb) return [];
    return this._all(this.songsDb, 'SELECT category, COUNT(*) as count FROM songs GROUP BY category ORDER BY count DESC');
  }

  // ═════════════════════════════════════════════════════════════════════════════
  // SETTINGS (per-profile stored in songs.db)
  // ═════════════════════════════════════════════════════════════════════════════

  async getSettings() {
    await this._awaitReady(); if (!this.songsDb) return {};
    const r = this._get(this.songsDb, 'SELECT value FROM cache WHERE key = ?', ['settings']);
    if (r) { try { return JSON.parse(r.value); } catch {} }
    return {};
  }

  async saveSettings(settings) {
    await this._awaitReady(); if (!this.songsDb) return;
    this._run(this.songsDb, 'INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)', ['settings', JSON.stringify(settings)]);
  }

  // ═════════════════════════════════════════════════════════════════════════════
  // MAINTENANCE
  // ═════════════════════════════════════════════════════════════════════════════

  async vacuum() {
    await this._awaitReady();
    if (this.songsDb) this._exec(this.songsDb, 'VACUUM');
    if (this.bibleDb) this._exec(this.bibleDb, 'VACUUM');
    this._saveSongs();
    this._saveBible();
  }

  async reindex() {
    await this._awaitReady();
    if (this.songsDb) {
      try { this._exec(this.songsDb, 'INSERT INTO songs_fts(songs_fts) VALUES(\'rebuild\')'); } catch {}
    }
    if (this.bibleDb) {
      try { this._exec(this.bibleDb, 'INSERT INTO verses_fts(verses_fts) VALUES(\'rebuild\')'); } catch {}
    }
  }

  close() {
    if (this.songsDb) { this._saveSongs(); this.songsDb.close(); }
    if (this.bibleDb) { this._saveBible(); this.bibleDb.close(); }
  }
}

module.exports = Database;
