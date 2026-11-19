const { app, BrowserWindow, ipcMain, screen, dialog, nativeTheme, Menu, globalShortcut } = require('electron');
const path = require('path');
const fs = require('fs');
const Database = require('./src/main/database');
const DisplayManager = require('./src/main/display-manager');
const RemoteServer = require('./src/main/remote-server');
const { importFile, searchOnlineSongs, translateText } = require('./src/main/import-parsers');

try { app.setName('cantio-electron'); } catch {}
const userDataPath = app.getPath('userData');
const profilesPath = path.join(userDataPath, 'profiles');
const logsPath = path.join(userDataPath, 'logs');
let activeProfile = null;
let activeProfileSettings = {};
let db = null;
let displayManager = null;
let remoteServer = null;
let mainWindow = null;

function ensureDir(dir) { if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true }); }
function log(...args) {
  const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
  const line = `[${ts}] ${args.join(' ')}\n`;
  ensureDir(logsPath);
  fs.appendFileSync(path.join(logsPath, 'cantio.log'), line);
}

// ═════════════════════════════════════════════════════════════════════════════
// PROFILE MANAGEMENT
// ═════════════════════════════════════════════════════════════════════════════

function getProfiles() {
  ensureDir(profilesPath);
  const dirs = fs.readdirSync(profilesPath, { withFileTypes: true })
    .filter(d => d.isDirectory())
    .map(d => d.name);
  if (dirs.length === 0) {
    const def = path.join(profilesPath, 'Default');
    fs.mkdirSync(def, { recursive: true });
    fs.writeFileSync(path.join(def, 'settings.json'), JSON.stringify({ language: 'ro' }));
    return ['Default'];
  }
  return dirs;
}

function loadProfileInfo(name) {
  const settingsPath = path.join(profilesPath, name, 'settings.json');
  let settings = {};
  if (fs.existsSync(settingsPath)) {
    try { settings = JSON.parse(fs.readFileSync(settingsPath, 'utf-8')); } catch {}
  }
  let password = '';
  const pwdPath = path.join(profilesPath, name, '.password');
  if (fs.existsSync(pwdPath)) {
    try { password = fs.readFileSync(pwdPath, 'utf-8').trim(); } catch {}
  }
  return { name, settings, hasPassword: !!password };
}

function loadProfile(name) {
  activeProfile = name;
  const profileDir = path.join(profilesPath, name);
  ensureDir(profileDir);
  if (db) db.close();
  db = new Database(profileDir);
  return loadProfileInfo(name);
}

function getSettingsPath() {
  return activeProfile ? path.join(profilesPath, activeProfile, 'settings.json') : null;
}

function readSettings() {
  const sp = getSettingsPath();
  if (!sp) return {};
  try { return JSON.parse(fs.readFileSync(sp, 'utf-8')); } catch { return {}; }
}

function writeSettings(settings) {
  const sp = getSettingsPath();
  if (!sp) return;
  ensureDir(path.dirname(sp));
  fs.writeFileSync(sp, JSON.stringify(settings, null, 2));
}

// ═════════════════════════════════════════════════════════════════════════════
// WINDOW
// ═════════════════════════════════════════════════════════════════════════════

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 600,
    title: 'Cantio',
    icon: path.join(__dirname, 'src', 'assets', 'icon.png'),
    backgroundColor: '#11111b',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: true,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    const profiles = getProfiles();
    const profileInfo = loadProfile(profiles[0]);
    mainWindow.webContents.send('profile-loaded', profileInfo);
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ═════════════════════════════════════════════════════════════════════════════
// IPC: PROFILES
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('profiles:list', () => getProfiles().map(p => loadProfileInfo(p)));

ipcMain.handle('profiles:load', (_, name) => {
  return loadProfile(name);
});

ipcMain.handle('profiles:create', (_, name) => {
  const dir = path.join(profilesPath, name);
  if (fs.existsSync(dir)) return { error: 'Profile already exists' };
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'settings.json'), JSON.stringify({ language: 'ro' }));
  log('Profile created:', name);
  return { name, settings: { language: 'ro' } };
});

ipcMain.handle('profiles:delete', (_, name) => {
  if (name === 'Default') return { error: 'Cannot delete Default profile' };
  const dir = path.join(profilesPath, name);
  if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true });
  log('Profile deleted:', name);
  return { ok: true };
});

ipcMain.handle('profiles:rename', (_, oldName, newName) => {
  if (newName === 'Default' || oldName === 'Default') return { error: 'Cannot rename Default' };
  const oldDir = path.join(profilesPath, oldName);
  const newDir = path.join(profilesPath, newName);
  if (!fs.existsSync(oldDir)) return { error: 'Profile not found' };
  if (fs.existsSync(newDir)) return { error: 'Target name already exists' };
  fs.renameSync(oldDir, newDir);
  log('Profile renamed:', oldName, '->', newName);
  return { ok: true };
});

ipcMain.handle('profiles:setPassword', (_, name, password) => {
  const dir = path.join(profilesPath, name);
  if (!fs.existsSync(dir)) return { error: 'Profile not found' };
  const pwdPath = path.join(dir, '.password');
  if (password) {
    const crypto = require('crypto');
    const hash = crypto.createHash('sha256').update(password).digest('hex');
    fs.writeFileSync(pwdPath, hash);
  } else {
    if (fs.existsSync(pwdPath)) fs.unlinkSync(pwdPath);
  }
  return { ok: true };
});

ipcMain.handle('profiles:checkPassword', (_, name, password) => {
  const pwdPath = path.join(profilesPath, name, '.password');
  if (!fs.existsSync(pwdPath)) return { ok: true };
  const crypto = require('crypto');
  const hash = crypto.createHash('sha256').update(password).digest('hex');
  const stored = fs.readFileSync(pwdPath, 'utf-8').trim();
  return { ok: hash === stored };
});

ipcMain.handle('profiles:setRestriction', (_, name, key, value) => {
  const dir = path.join(profilesPath, name);
  const restPath = path.join(dir, 'restrictions.json');
  let restrictions = {};
  if (fs.existsSync(restPath)) {
    try { restrictions = JSON.parse(fs.readFileSync(restPath, 'utf-8')); } catch {}
  }
  if (value === null) {
    delete restrictions[key];
  } else {
    restrictions[key] = value;
  }
  fs.writeFileSync(restPath, JSON.stringify(restrictions, null, 2));
  return { ok: true };
});

ipcMain.handle('profiles:getRestrictions', (_, name) => {
  const dir = path.join(profilesPath, name);
  const restPath = path.join(dir, 'restrictions.json');
  if (!fs.existsSync(restPath)) return {};
  try { return JSON.parse(fs.readFileSync(restPath, 'utf-8')); } catch { return {}; }
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: SETTINGS
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('settings:get', () => readSettings());

ipcMain.handle('settings:set', (_, settings) => {
  const merged = { ...readSettings(), ...settings };
  writeSettings(merged);
  if (displayManager) displayManager.broadcastSettings(merged);
  return merged;
});

ipcMain.handle('settings:getAll', () => {
  const s = readSettings();
  return {
    ...s,
    profilesPath,
    userDataPath,
    logsPath,
    version: app.getVersion(),
  };
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: DATABASE — SONGS
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('db:songs:search', (_, query, page, limit) => db.searchSongs(query, page, limit));
ipcMain.handle('db:songs:getAll', (_, page, limit) => db.getAllSongs(page, limit));
ipcMain.handle('db:songs:getById', (_, id) => db.getSongById(id));
ipcMain.handle('db:songs:save', (_, song) => db.saveSong(song));
ipcMain.handle('db:songs:delete', (_, id) => db.deleteSong(id));
ipcMain.handle('db:songs:getCategories', () => db.getCategories());
ipcMain.handle('db:songs:getByCategory', (_, cat, page, limit) => db.getSongsByCategory(cat, page, limit));
ipcMain.handle('db:songs:getCount', () => db.getSongCount());
ipcMain.handle('db:songs:add', (_, title, content, slides, author, category, language) =>
  db.addSong(title, content, slides, author, category, language));
ipcMain.handle('db:songs:countByCategory', () => db.getSongCountByCategory());
ipcMain.handle('db:songs:exportJson', () => db.exportSongsJson());
ipcMain.handle('db:songs:importJson', (_, json) => db.importSongsJson(json));

// ═════════════════════════════════════════════════════════════════════════════
// IPC: DATABASE — BIBLE
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('db:bible:search', (_, query, translation) => db.searchBible(query, translation));
ipcMain.handle('db:bible:getBooks', (_, translation) => db.getBibleBooks(translation));
ipcMain.handle('db:bible:getDefaultBooks', () => db.getDefaultBibleBooks());
ipcMain.handle('db:bible:getChapters', (_, book, translation) => db.getBibleChapters(book, translation));
ipcMain.handle('db:bible:getVerses', (_, book, chapter, translation) => db.getBibleVerses(book, chapter, translation));
ipcMain.handle('db:bible:getVerse', (_, book, chapter, verse, translation) => db.getBibleVerse(book, chapter, verse, translation));
ipcMain.handle('db:bible:getTranslations', () => db.getBibleTranslations());
ipcMain.handle('db:bible:importData', (_, books, verses, translation) => db.importBibleData(books, verses, translation));
ipcMain.handle('db:bible:initDefaultBooks', (_, translation) => db.initDefaultBibleBooks(translation));

// ═════════════════════════════════════════════════════════════════════════════
// IPC: DATABASE — PLAYLISTS
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('db:playlists:getAll', () => db.getAllPlaylists());
ipcMain.handle('db:playlists:getById', (_, id) => db.getPlaylistById(id));
ipcMain.handle('db:playlists:save', (_, p) => db.savePlaylist(p));
ipcMain.handle('db:playlists:delete', (_, id) => db.deletePlaylist(id));

// ═════════════════════════════════════════════════════════════════════════════
// IPC: DATABASE — PRESENTATIONS
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('db:presentations:getAll', () => db.getAllPresentations());
ipcMain.handle('db:presentations:getById', (_, id) => db.getPresentation(id));
ipcMain.handle('db:presentations:save', (_, p) => db.savePresentation(p));
ipcMain.handle('db:presentations:delete', (_, id) => db.deletePresentation(id));

// ═════════════════════════════════════════════════════════════════════════════
// IPC: DATABASE — SERVICE
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('db:service:getItems', (_, serviceId) => db.getServiceItems(serviceId));
ipcMain.handle('db:service:saveItems', (_, serviceId, items) => db.saveServiceItems(serviceId, items));
ipcMain.handle('db:service:clear', (_, serviceId) => db.clearService(serviceId));

// ═════════════════════════════════════════════════════════════════════════════
// IPC: DATABASE — CATEGORIES
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('db:categories:getAll', () => db.getAllCategories());
ipcMain.handle('db:categories:add', (_, name, color) => db.addCategory(name, color));
ipcMain.handle('db:categories:delete', (_, name) => db.deleteCategory(name));

// ═════════════════════════════════════════════════════════════════════════════
// IPC: DATABASE — CACHE
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('db:cache:get', (_, key) => db.cacheGet(key));
ipcMain.handle('db:cache:set', (_, key, value, ttl) => db.cacheSet(key, value, ttl));
ipcMain.handle('db:cache:delete', (_, key) => db.cacheDelete(key));

// ═════════════════════════════════════════════════════════════════════════════
// IPC: DATABASE — MAINTENANCE
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('db:checkIntegrity', () => db.checkIntegrity());
ipcMain.handle('db:vacuum', () => db.vacuum());
ipcMain.handle('db:reindex', () => db.reindex());

// ═════════════════════════════════════════════════════════════════════════════
// IPC: DISPLAY
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('display:getScreens', () => screen.getAllDisplays().map((d, i) => ({
  index: i, id: d.id, label: d.label || `Display ${i+1}`,
  width: d.bounds.width, height: d.bounds.height,
  x: d.bounds.x, y: d.bounds.y,
  primary: d.id === screen.getPrimaryDisplay().id,
  scaleFactor: d.scaleFactor,
})));

ipcMain.handle('display:show', (_, { screenIndex, text, format, metadata, transition }) => {
  if (!displayManager) displayManager = new DisplayManager();
  displayManager.showText({ screenIndex, text, format, metadata, transition, settings: readSettings() });
});

ipcMain.handle('display:black', (_, { screenIndex }) => {
  if (displayManager) displayManager.black(screenIndex);
});

ipcMain.handle('display:ticker', (_, { text, speed, color }) => {
  if (!displayManager) displayManager = new DisplayManager();
  displayManager.ticker(text, speed, color);
});

ipcMain.handle('display:hideTicker', () => {
  if (displayManager) displayManager.hideTicker();
});

ipcMain.handle('display:clock', (_, { active, color, format }) => {
  if (displayManager) displayManager.clock(active, color, format);
});

ipcMain.handle('display:timer', (_, { seconds, color }) => {
  if (displayManager) displayManager.timer(seconds, color);
});

ipcMain.handle('display:stopTimer', () => {
  if (displayManager) displayManager.stopTimer();
});

ipcMain.handle('display:logo', (_, { path: logoPath }) => {
  if (!displayManager) displayManager = new DisplayManager();
  displayManager.logo(logoPath);
});

ipcMain.handle('display:hideLogo', () => {
  if (displayManager) displayManager.hideLogo();
});

ipcMain.handle('display:freeze', (_, { freeze }) => {
  if (displayManager) displayManager.freeze(freeze);
});

ipcMain.handle('display:projectorOff', (_, { off }) => {
  if (displayManager) displayManager.projectorOff(off);
});

ipcMain.handle('display:open', (_, opts) => {
  if (!displayManager) displayManager = new DisplayManager();
  return displayManager.openWindow(opts);
});

ipcMain.handle('display:close', (_, { windowId }) => {
  if (displayManager) displayManager.closeWindow(windowId);
});

ipcMain.handle('display:closeAll', () => {
  if (displayManager) displayManager.closeAll();
});

ipcMain.handle('display:clearText', (_, { screenIndex }) => {
  if (displayManager) displayManager.clearText(screenIndex);
});

ipcMain.handle('display:setSettings', (_, { screenIndex, settings }) => {
  if (displayManager) displayManager.setSettings(screenIndex, settings);
});

ipcMain.handle('display:getState', () => {
  if (displayManager) return displayManager.getState();
  return {};
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: STAGE MONITOR
// ═════════════════════════════════════════════════════════════════════════════

let stageWindow = null;

ipcMain.handle('stage:open', () => {
  if (stageWindow && !stageWindow.isDestroyed()) { stageWindow.focus(); return; }
  stageWindow = new BrowserWindow({
    width: 600, height: 500,
    title: 'Cantio — Stage Monitor',
    alwaysOnTop: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  stageWindow.loadFile(path.join(__dirname, 'src', 'stage-monitor.html'));
  stageWindow.on('closed', () => { stageWindow = null; });
});

ipcMain.handle('stage:close', () => {
  if (stageWindow) { stageWindow.close(); stageWindow = null; }
});

ipcMain.handle('stage:send', (_, data) => {
  if (stageWindow && !stageWindow.isDestroyed()) {
    stageWindow.webContents.send('stage-data', data);
  }
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: REMOTE SERVER
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('remote:start', (_, { port } = {}) => {
  if (remoteServer) remoteServer.stop();
  remoteServer = new RemoteServer(port || 5050, mainWindow);
  remoteServer.start();
  return remoteServer.getUrl();
});

ipcMain.handle('remote:stop', () => {
  if (remoteServer) remoteServer.stop();
  remoteServer = null;
});

ipcMain.handle('remote:status', () => {
  return remoteServer ? remoteServer.getStatus() : { running: false };
});

ipcMain.handle('remote:getUrl', () => {
  return remoteServer ? remoteServer.getUrl() : null;
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: FILE DIALOGS
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('dialog:openFile', async (_, opts) => {
  return dialog.showOpenDialog(mainWindow, opts);
});

ipcMain.handle('dialog:saveFile', async (_, opts) => {
  return dialog.showSaveDialog(mainWindow, opts);
});

ipcMain.handle('dialog:openDirectory', async () => {
  return dialog.showOpenDialog(mainWindow, { properties: ['openDirectory'] });
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: IMPORT
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('import:file', async (_, filePath) => {
  try {
    const result = await importFile(filePath);
    return result;
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle('import:folder', async (_, folderPath) => {
  const supported = ['.txt', '.docx', '.pdf', '.json', '.xml', '.vpc', '.ewsx', '.db'];
  const files = fs.readdirSync(folderPath).filter(f =>
    supported.includes(path.extname(f).toLowerCase())
  ).map(f => path.join(folderPath, f));
  const results = [];
  const errors = [];
  for (const file of files) {
    try {
      const r = await importFile(file);
      results.push({ file, result: r });
    } catch (e) {
      errors.push({ file, error: e.message });
    }
  }
  return { results, errors };
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: ONLINE SONGS
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('online:search', async (_, { query, source }) => {
  try {
    return await searchOnlineSongs(query, source);
  } catch (e) {
    return { error: e.message };
  }
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: TRANSLATION
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('translate:text', async (_, { text, targetLang }) => {
  try {
    return await translateText(text, targetLang);
  } catch (e) {
    return { error: e.message };
  }
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: SERVICE FILES (.gps)
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('service:save', async (_, { items, path: filePath }) => {
  const AdmZip = require('adm-zip');
  try {
    const zip = new AdmZip();
    zip.addFile('service.json', Buffer.from(JSON.stringify({ items, version: '2.0' }, null, 2), 'utf-8'));
    zip.addLocalFile(getSettingsPath(), 'settings.json');
    zip.writeZip(filePath);
    return { ok: true };
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle('service:load', async (_, filePath) => {
  try {
    const AdmZip = require('adm-zip');
    const zip = new AdmZip(filePath);
    const entry = zip.getEntry('service.json');
    if (!entry) return { error: 'Invalid service file' };
    const data = JSON.parse(entry.getData().toString('utf-8'));
    return { items: data.items || [] };
  } catch (e) {
    return { error: e.message };
  }
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: PDF EXPORT
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('export:pdf', async (_, { songs, filePath }) => {
  try {
    let html = '<html><head><meta charset="utf-8"><style>';
    html += 'body{font-family:Segoe UI,Arial,sans-serif;padding:40px}';
    html += 'h1{font-size:24px;color:#333;border-bottom:2px solid #5294e2;padding-bottom:8px}';
    html += '.song{margin-bottom:30px;page-break-inside:avoid}';
    html += '.title{font-size:18px;font-weight:bold;color:#1a1a1a}';
    html += '.author{font-size:12px;color:#888;margin-bottom:8px}';
    html += '.lyrics{font-size:14px;line-height:1.6;white-space:pre-wrap}';
    html += '</style></head><body>';
    html += '<h1>Cantio — Listă cântări</h1>';
    for (const s of songs) {
      html += `<div class="song"><div class="title">${s.title}</div>`;
      if (s.author) html += `<div class="author">${s.author}</div>`;
      html += `<div class="lyrics">${s.lyrics || s.content || ''}</div></div>`;
    }
    html += '</body></html>';
    const pdf = require('html-pdf');
    await new Promise((resolve, reject) => {
      pdf.create(html).toFile(filePath, (err, res) => {
        if (err) reject(err); else resolve(res);
      });
    });
    return { ok: true };
  } catch (e) {
    return { error: e.message };
  }
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: MEDIA / CAMERA
// ═════════════════════════════════════════════════════════════════════════════

let mediaProcess = null;

ipcMain.handle('media:startVideo', async (_, filePath) => {
  try {
    const { spawn } = require('child_process');
    if (mediaProcess) mediaProcess.kill();
    const ffmpegPath = 'ffmpeg';
    mediaProcess = spawn(ffmpegPath, [
      '-re', '-i', filePath,
      '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '960x540',
      '-r', '30', 'pipe:1',
    ]);
    mainWindow.webContents.send('media:videoStarted', { path: filePath });
    return { ok: true };
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle('media:stopVideo', () => {
  if (mediaProcess) { mediaProcess.kill(); mediaProcess = null; }
  mainWindow.webContents.send('media:videoStopped');
  return { ok: true };
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: SYSTEM
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('system:getInfo', () => ({
  version: app.getVersion(),
  electron: process.versions.electron,
  node: process.versions.node,
  chrome: process.versions.chrome,
  platform: process.platform,
  userData: userDataPath,
  profilesPath,
  logsPath,
}));

ipcMain.handle('system:openFolder', (_, folderPath) => {
  const { shell } = require('electron');
  shell.openPath(folderPath);
});

ipcMain.handle('system:openExternal', (_, url) => {
  const { shell } = require('electron');
  shell.openExternal(url);
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: WINDOW
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('window:minimize', () => { if (mainWindow) mainWindow.minimize(); });
ipcMain.handle('window:maximize', () => { if (mainWindow) { mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize(); } });
ipcMain.handle('window:close', () => { if (mainWindow) mainWindow.close(); });
ipcMain.handle('window:isMaximized', () => mainWindow ? mainWindow.isMaximized() : false);
ipcMain.handle('window:setSize', (_, w, h) => { if (mainWindow) mainWindow.setSize(w, h); });
ipcMain.handle('window:fullscreen', (_, fs) => { if (mainWindow) mainWindow.setFullScreen(fs); });

// ═════════════════════════════════════════════════════════════════════════════
// IPC: KEYBOARD SHORTCUTS
// ═════════════════════════════════════════════════════════════════════════════

let registeredShortcuts = {};

ipcMain.handle('shortcuts:register', (_, { accelerator, command }) => {
  try {
    globalShortcut.unregister(accelerator);
    globalShortcut.register(accelerator, () => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('shortcut-triggered', command);
      }
    });
    registeredShortcuts[accelerator] = command;
    return { ok: true };
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle('shortcuts:unregister', (_, accelerator) => {
  globalShortcut.unregister(accelerator);
  delete registeredShortcuts[accelerator];
  return { ok: true };
});

ipcMain.handle('shortcuts:unregisterAll', () => {
  globalShortcut.unregisterAll();
  registeredShortcuts = {};
  return { ok: true };
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: THEMES
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('themes:getPath', () => {
  const themesPath = path.join(userDataPath, 'themes');
  ensureDir(themesPath);
  return themesPath;
});

ipcMain.handle('themes:list', () => {
  const themesPath = path.join(userDataPath, 'themes');
  ensureDir(themesPath);
  const dirs = fs.readdirSync(themesPath, { withFileTypes: true })
    .filter(d => d.isDirectory())
    .map(d => {
      const cfgPath = path.join(themesPath, d.name, 'theme.json');
      let cfg = {};
      if (fs.existsSync(cfgPath)) {
        try { cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf-8')); } catch {}
      }
      return { name: d.name, ...cfg };
    });
  return dirs;
});

ipcMain.handle('themes:save', (_, { name, data }) => {
  const themesPath = path.join(userDataPath, 'themes');
  const dir = path.join(themesPath, name);
  ensureDir(dir);
  fs.writeFileSync(path.join(dir, 'theme.json'), JSON.stringify(data, null, 2));
  return { ok: true };
});

ipcMain.handle('themes:delete', (_, name) => {
  const dir = path.join(userDataPath, 'themes', name);
  if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true });
  return { ok: true };
});

// ═════════════════════════════════════════════════════════════════════════════
// IPC: CLOUD (Supabase)
// ═════════════════════════════════════════════════════════════════════════════

ipcMain.handle('cloud:upload', async (_, { url, key, data }) => {
  try {
    const response = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${key}` },
      body: JSON.stringify(data),
    });
    return { ok: response.ok, status: response.status };
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle('cloud:download', async (_, { url, key }) => {
  try {
    const response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${key}` },
    });
    if (!response.ok) return { error: `HTTP ${response.status}` };
    const data = await response.json();
    return { ok: true, data };
  } catch (e) {
    return { error: e.message };
  }
});

// ═════════════════════════════════════════════════════════════════════════════
// APP LIFECYCLE
// ═════════════════════════════════════════════════════════════════════════════

app.whenReady().then(() => {
  const { session } = require('electron');
  session.defaultSession.setPermissionRequestHandler((wc, permission, callback) => {
    if (['media', 'camera', 'microphone'].includes(permission)) {
      callback(true);
    } else {
      callback(false);
    }
  });
  createMainWindow();
  log('Cantio started, version:', app.getVersion());
});

app.on('window-all-closed', () => {
  globalShortcut.unregisterAll();
  if (remoteServer) remoteServer.stop();
  if (db) db.close();
  if (displayManager) displayManager.closeAll();
  app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
});

process.on('uncaughtException', (e) => {
  if (e.code === 'EPIPE' || e.message?.includes('pipe')) return;
  try {
    fs.appendFileSync(path.join(userDataPath, 'error.log'), e.stack + '\n');
  } catch {}
  log('Uncaught exception:', e.message);
});
