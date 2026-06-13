/**
 * One-time migration script: copies data from the existing Python Cantio app
 * (at C:\Users\tudor\Cantio\profiles\{profile}) to the Electron app's format.
 * Run: node migrate-data.js <profile_name>
 * Example: node migrate-data.js Default
 */
const initSqlJs = require('sql.js');
const path = require('path');
const fs = require('fs');
const os = require('os');

const OLD_DATA_DIR = path.join(os.homedir(), 'Cantio', 'profiles');

async function migrateSongs(oldDbPath, newDbPath) {
  console.log('  Reading songs from:', oldDbPath);
  const oldBuffer = fs.readFileSync(oldDbPath);
  const SQL = await initSqlJs();
  const oldDb = new SQL.Database(oldBuffer);

  // Read songs table (ignore FTS5 virtual tables)
  const rows = oldDb.exec('SELECT id, title, author, category, language, content, slides, notes, created_at FROM songs ORDER BY id');
  const songs = rows[0]?.values || [];
  console.log(`  Found ${songs.length} songs`);

  // Create new songs database with Electron schema
  const newDb = new SQL.Database();
  newDb.run(`CREATE TABLE IF NOT EXISTS songs (
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
  newDb.run(`CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    items TEXT DEFAULT '[]',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )`);
  newDb.run(`CREATE TABLE IF NOT EXISTS presentations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    data TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )`);

  const insertStmt = newDb.prepare(`INSERT INTO songs (id, title, author, category, language, lyrics, slides, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`);
  newDb.run('BEGIN TRANSACTION');
  for (const s of songs) {
    insertStmt.bind([s[0], s[1], s[2] || '', s[3] || '', s[4] || 'ro', s[5] || '', s[6] || '', s[7] || '', s[8] || null]);
    insertStmt.step();
    insertStmt.reset();
  }
  newDb.run('COMMIT');
  insertStmt.free();

  fs.writeFileSync(newDbPath, Buffer.from(newDb.export()));
  newDb.close();
  oldDb.close();
  console.log(`  Written: ${newDbPath} (${(fs.statSync(newDbPath).size / 1024 / 1024).toFixed(1)} MB)`);
}

async function migrateBible(oldDbPath, newDbPath) {
  console.log('  Reading bible from:', oldDbPath);
  const oldBuffer = fs.readFileSync(oldDbPath);
  const SQL = await initSqlJs();
  const oldDb = new SQL.Database(oldBuffer);

  const newDb = new SQL.Database();
  newDb.run(`CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL,
    abbreviation TEXT, testament INTEGER DEFAULT 1
  )`);
  newDb.run(`CREATE TABLE IF NOT EXISTS verses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL, chapter INTEGER NOT NULL,
    verse INTEGER NOT NULL, text TEXT NOT NULL,
    translation TEXT DEFAULT 'niv',
    FOREIGN KEY (book_id) REFERENCES books(id)
  )`);
  newDb.run(`CREATE TABLE IF NOT EXISTS translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
    language TEXT DEFAULT 'ro'
  )`);
  newDb.run('CREATE INDEX IF NOT EXISTS idx_verses_ref ON verses(book_id, chapter, verse)');

  // Books
  const oldBooks = oldDb.exec('SELECT id, name, abbreviation, testament, book_order FROM bible_books ORDER BY id');
  const books = oldBooks[0]?.values || [];
  console.log(`  Found ${books.length} books`);
  const bookMap = {};

  const insBook = newDb.prepare('INSERT INTO books (id, name, abbreviation, testament) VALUES (?, ?, ?, ?)');
  newDb.run('BEGIN TRANSACTION');
  for (const b of books) {
    const test = b[3] === 'OT' ? 1 : 2;
    insBook.bind([b[0], b[1], b[2], test]);
    insBook.step();
    insBook.reset();
    bookMap[b[0]] = b[1];
  }
  newDb.run('COMMIT');
  insBook.free();

  // Verses
  const oldVerses = oldDb.exec('SELECT id, book_id, chapter, verse, text, translation FROM bible_verses ORDER BY id');
  const vers = oldVerses[0]?.values || [];
  console.log(`  Found ${vers.length} verses`);

  const insVerse = newDb.prepare('INSERT INTO verses (book_id, chapter, verse, text, translation) VALUES (?, ?, ?, ?, ?)');
  newDb.run('BEGIN TRANSACTION');
  for (const v of vers) {
    insVerse.bind([v[1], v[2], v[3], v[4], v[5] || 'VBA']);
    insVerse.step();
    insVerse.reset();
  }
  newDb.run('COMMIT');
  insVerse.free();

  // Translations
  const oldTranslations = oldDb.exec('SELECT id, name, abbreviation, language, is_active, is_secondary FROM bible_translations ORDER BY id');
  const trans = oldTranslations[0]?.values || [];
  console.log(`  Found ${trans.length} translations`);
  if (trans.length > 0) {
    const insTr = newDb.prepare('INSERT INTO translations (id, code, name, language) VALUES (?, ?, ?, ?)');
    newDb.run('BEGIN TRANSACTION');
    for (const t of trans) {
      insTr.bind([t[0], t[2] || t[1], t[1], t[3] || 'ro']);
      insTr.step();
      insTr.reset();
    }
    newDb.run('COMMIT');
    insTr.free();
  }

  fs.writeFileSync(newDbPath, Buffer.from(newDb.export()));
  newDb.close();
  oldDb.close();
  console.log(`  Written: ${newDbPath} (${(fs.statSync(newDbPath).size / 1024 / 1024).toFixed(1)} MB)`);
}

async function main() {
  const profile = process.argv[2];
  if (!profile) {
    const dirs = fs.readdirSync(OLD_DATA_DIR, { withFileTypes: true })
      .filter(d => d.isDirectory())
      .map(d => d.name);
    console.log('Usage: node migrate-data.js <profile_name>');
    console.log('Available profiles:', dirs.join(', '));
    process.exit(1);
  }

  const oldProfileDir = path.join(OLD_DATA_DIR, profile);
  if (!fs.existsSync(oldProfileDir)) {
    console.error(`Profile not found: ${oldProfileDir}`);
    process.exit(1);
  }

  const newProfileDir = path.join(process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'), 'cantio-electron', 'profiles', profile);
  fs.mkdirSync(newProfileDir, { recursive: true });

  console.log(`Migrating profile "${profile}"`);
  console.log(`  From: ${oldProfileDir}`);
  console.log(`  To:   ${newProfileDir}`);

  // Migrate songs
  const oldSongsDb = path.join(oldProfileDir, 'songs.db');
  const newSongsDb = path.join(newProfileDir, 'songs.db');
  if (fs.existsSync(oldSongsDb)) {
    await migrateSongs(oldSongsDb, newSongsDb);
  } else {
    console.log('  No songs.db found, skipping');
  }

  // Migrate bible
  const oldBibleDb = path.join(oldProfileDir, 'bible.db');
  const newBibleDb = path.join(newProfileDir, 'bible.db');
  if (fs.existsSync(oldBibleDb)) {
    await migrateBible(oldBibleDb, newBibleDb);
  } else {
    console.log('  No bible.db found, skipping');
  }

  // Copy settings.json
  const oldSettings = path.join(oldProfileDir, 'settings.json');
  const newSettings = path.join(newProfileDir, 'settings.json');
  if (fs.existsSync(oldSettings)) {
    fs.copyFileSync(oldSettings, newSettings);
    console.log('  Copied settings.json');
  }

  console.log('Migration complete!');
}

main().catch(e => { console.error('Migration failed:', e.message, e.stack); process.exit(1); });
