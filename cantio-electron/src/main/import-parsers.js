const fs = require('fs');
const path = require('path');

function importFile(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const content = fs.readFileSync(filePath, 'utf-8');
  const fileName = path.basename(filePath, ext);

  switch (ext) {
    case '.txt':
      return parseTxt(content, fileName);
    case '.json':
      return parseJson(content, fileName);
    default:
      return { error: `Unsupported file format: ${ext}`, songs: [] };
  }
}

function parseTxt(content, defaultTitle) {
  const lines = content.split('\n').filter(l => l.trim());
  if (lines.length === 0) return { error: 'Empty file', songs: [] };

  const songs = [];
  let currentSong = { title: defaultTitle, author: '', lyrics: '', slides: '' };
  let currentLyrics = [];
  let currentSection = 'v1';

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    const sectionMatch = trimmed.match(/^\[(.+)\]$/);
    if (sectionMatch) {
      if (currentLyrics.length > 0) {
        currentSong.lyrics = currentLyrics.join('\n');
        songs.push({ ...currentSong });
      }
      currentSong = { title: trimmed, author: '', lyrics: '', slides: '' };
      currentLyrics = [];
      currentSection = sectionMatch[1].toLowerCase();
      continue;
    }

    if (trimmed.toLowerCase().startsWith('title:') || trimmed.toLowerCase().startsWith('t:')) {
      currentSong.title = trimmed.split(':').slice(1).join(':').trim();
    } else if (trimmed.toLowerCase().startsWith('author:') || trimmed.toLowerCase().startsWith('a:')) {
      currentSong.author = trimmed.split(':').slice(1).join(':').trim();
    } else {
      currentLyrics.push(trimmed);
    }
  }

  if (currentLyrics.length > 0) {
    currentSong.lyrics = currentLyrics.join('\n');
    songs.push({ ...currentSong });
  }

  return { songs, format: 'txt' };
}

function parseJson(content, defaultTitle) {
  try {
    const data = JSON.parse(content);
    const songs = [];
    if (Array.isArray(data)) {
      data.forEach(item => {
        songs.push({
          title: item.title || defaultTitle,
          author: item.author || '',
          lyrics: item.lyrics || '',
          category: item.category || '',
          slides: item.slides || '',
        });
      });
    } else if (data.title || data.lyrics) {
      songs.push({
        title: data.title || defaultTitle,
        author: data.author || '',
        lyrics: data.lyrics || '',
        category: data.category || '',
        slides: data.slides || '',
      });
    }
    return { songs, format: 'json' };
  } catch (e) {
    return { error: `Invalid JSON: ${e.message}`, songs: [] };
  }
}

async function searchOnlineSongs(query, source = 'resursecrestine') {
  try {
    const https = require('https');
    return new Promise((resolve) => {
      if (source === 'resursecrestine') {
        const url = `https://www.resursecrestine.ro/cauta/${encodeURIComponent(query)}/cantece`;
        https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
          let data = '';
          res.on('data', chunk => data += chunk);
          res.on('end', () => {
            const results = [];
            const titleRegex = /<a[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)<\/a>/gi;
            let match;
            while ((match = titleRegex.exec(data)) !== null) {
              results.push({ title: match[1].trim(), source: 'resursecrestine.ro' });
            }
            resolve(results.slice(0, 50));
          });
        }).on('error', () => resolve([]));
      } else {
        resolve([]);
      }
    });
  } catch {
    return [];
  }
}

async function translateText(text, targetLang = 'ro') {
  try {
    const https = require('https');
    return new Promise((resolve) => {
      const q = encodeURIComponent(text);
      const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=${targetLang}&dt=t&q=${q}`;
      https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try {
            const parsed = JSON.parse(data);
            const translated = parsed[0]?.map(s => s[0]).join('') || text;
            resolve({ translated, original: text });
          } catch {
            resolve({ translated: text, original: text });
          }
        });
      }).on('error', () => resolve({ translated: text, original: text }));
    });
  } catch {
    return { translated: text, original: text };
  }
}

module.exports = { importFile, searchOnlineSongs, translateText };
