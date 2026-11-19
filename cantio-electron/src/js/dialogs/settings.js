Dialogs = Dialogs || {};
Dialogs.settings = {
  async open() {
    const settings = appState.get('settings') || {};
    const screens = await window.api.display.getScreens();
    const profiles = await window.api.db.profiles.list();
    const restrictions = appState.get('profile') ? await window.api.db.profiles.getRestrictions(appState.get('profile').name) : {};

    const html = `
      <div class="settings-dialog">
        <h2>Setări</h2>
        <div class="settings-tabs">
          <button class="settings-tab active" data-stab="display">Afișare</button>
          <button class="settings-tab" data-stab="text">Text</button>
          <button class="settings-tab" data-stab="overlays">Overlay</button>
          <button class="settings-tab" data-stab="windows">Ferestre</button>
          <button class="settings-tab" data-stab="interface">Interfață</button>
          <button class="settings-tab" data-stab="cloud">Cloud</button>
          <button class="settings-tab" data-stab="database">Bază date</button>
          <button class="settings-tab" data-stab="security">Securitate</button>
        </div>
        <div id="settings-content" class="settings-content">
          ${this.tabDisplay(settings, screens)}
        </div>
        <div class="dialog-buttons">
          <button class="btn btn-secondary" data-close="close">Închide</button>
          <button class="btn btn-primary" id="settings-save">Salvează</button>
        </div>
      </div>`;

    Utils.dialog(html, 700).then(() => {
      // Dialog closed
    });

    // Tab switching
    document.querySelectorAll('.settings-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const section = tab.dataset.stab;
        const content = document.getElementById('settings-content');
        if (content) {
          switch (section) {
            case 'display': content.innerHTML = this.tabDisplay(settings, screens); break;
            case 'text': content.innerHTML = this.tabText(settings); break;
            case 'overlays': content.innerHTML = this.tabOverlays(settings); break;
            case 'windows': content.innerHTML = this.tabWindows(settings, screens); break;
            case 'interface': content.innerHTML = this.tabInterface(settings); break;
            case 'cloud': content.innerHTML = this.tabCloud(settings); break;
            case 'database': content.innerHTML = this.tabDatabase(); break;
            case 'security': content.innerHTML = this.tabSecurity(settings, profiles, restrictions); break;
          }
          this.attachListeners(settings);
        }
      });
    });

    // Save
    document.getElementById('settings-save')?.addEventListener('click', () => {
      this.save(settings);
    });

    setTimeout(() => this.attachListeners(settings), 100);
  },

  tabDisplay(settings, screens) {
    return `
      <div class="settings-section">
        <h3>Afișare</h3>
        <label>Mod afișare
          <select id="set-display-mode" class="input">
            <option value="fullscreen" ${settings.displayMode === 'fullscreen' ? 'selected' : ''}>Ecran complet</option>
            <option value="windowed" ${settings.displayMode === 'windowed' ? 'selected' : ''}>Fereastră</option>
          </select>
        </label>
        <label>Ecran
          <select id="set-screen" class="input">
            ${screens.map((s, i) => `<option value="${i}" ${settings.screenIndex == i ? 'selected' : ''}>${s.label} (${s.width}x${s.height})</option>`).join('')}
          </select>
        </label>
        <label>Culoare fundal
          <input type="color" id="set-bg-color" class="input" value="${settings.bg_color || '#000000'}">
        </label>
        <label>Imagine fundal
          <input type="text" id="set-bg-image" class="input" placeholder="Cale imagine..." value="${settings.bg_image || ''}">
          <button class="btn btn-sm btn-secondary" id="set-bg-image-browse">📁</button>
        </label>
        <label>Video fundal
          <input type="text" id="set-bg-video" class="input" placeholder="Cale video..." value="${settings.bg_video || ''}">
          <button class="btn btn-sm btn-secondary" id="set-bg-video-browse">📁</button>
        </label>
        <label>Tranziție
          <select id="set-transition" class="input">
            <option value="crossfade" ${(settings.transition||'crossfade') === 'crossfade' ? 'selected' : ''}>Crossfade</option>
            <option value="fade" ${settings.transition === 'fade' ? 'selected' : ''}>Fade</option>
            <option value="slide_left" ${settings.transition === 'slide_left' ? 'selected' : ''}>Slide stânga</option>
            <option value="zoom_in" ${settings.transition === 'zoom_in' ? 'selected' : ''}>Zoom</option>
            <option value="instant" ${settings.transition === 'instant' ? 'selected' : ''}>Instant</option>
          </select>
        </label>
        <label>Durată tranziție (ms)
          <input type="number" id="set-transition-duration" class="input" value="${settings.transition_duration || 350}" min="0" max="2000">
        </label>
      </div>`;
  },

  tabText(settings) {
    return `
      <div class="settings-section">
        <h3>Text</h3>
        <label>Font
          <select id="set-font-family" class="input">
            ${['Arial', 'Segoe UI', 'Times New Roman', 'Georgia', 'Verdana', 'Tahoma', 'Consolas'].map(f =>
              `<option value="${f}" ${(settings.font_family||'Arial') === f ? 'selected' : ''}>${f}</option>`
            ).join('')}
          </select>
        </label>
        <label>Dimensiune font
          <input type="number" id="set-font-size" class="input" value="${settings.font_size || 48}" min="12" max="300">
        </label>
        <label>Culoare text
          <input type="color" id="set-text-color" class="input" value="${settings.text_color || '#ffffff'}">
        </label>
        <label>Culoare contur
          <input type="color" id="set-outline-color" class="input" value="${settings.outline_color || '#000000'}">
        </label>
        <label>Grosime contur
          <input type="number" id="set-outline-width" class="input" value="${settings.outline_width || 2}" min="0" max="20">
        </label>
        <label><input type="checkbox" id="set-text-shadow" ${settings.text_shadow !== 'false' ? 'checked' : ''}> Umbră text</label>
        <label><input type="checkbox" id="set-font-bold" ${settings.font_bold === 'true' ? 'checked' : ''}> Bold</label>
        <label><input type="checkbox" id="set-font-italic" ${settings.font_italic === 'true' ? 'checked' : ''}> Italic</label>
        <label>Aliniere
          <select id="set-text-align" class="input">
            <option value="center" ${(settings.text_align||'center') === 'center' ? 'selected' : ''}>Centrat</option>
            <option value="left" ${settings.text_align === 'left' ? 'selected' : ''}>Stânga</option>
            <option value="right" ${settings.text_align === 'right' ? 'selected' : ''}>Dreapta</option>
          </select>
        </label>
        <label>Aliniere verticală
          <select id="set-text-valign" class="input">
            <option value="center" ${(settings.text_valign||'center') === 'center' ? 'selected' : ''}>Centrat</option>
            <option value="top" ${settings.text_valign === 'top' ? 'selected' : ''}>Sus</option>
            <option value="bottom" ${settings.text_valign === 'bottom' ? 'selected' : ''}>Jos</option>
          </select>
        </label>
        <label>Margine
          <input type="number" id="set-margin" class="input" value="${settings.margin || 80}" min="0" max="400">
        </label>
        <label>Distanță linii
          <input type="number" id="set-line-spacing" class="input" value="${settings.line_spacing || 1.4}" min="0.5" max="3" step="0.1">
        </label>
        <label>Cuvinte sacre
          <input type="text" id="set-sacred-words" class="input" value="${settings.sacred_words || ''}" placeholder="ex: Domnul,Isus,Dumnezeu">
        </label>
        <label><input type="checkbox" id="set-sacred-enabled" ${settings.sacred_words_enabled === 'true' ? 'checked' : ''}> Activează cuvinte sacre</label>
      </div>`;
  },

  tabOverlays(settings) {
    return `
      <div class="settings-section">
        <h3>Ticker</h3>
        <label>Viteză ticker
          <input type="number" id="set-ticker-speed" class="input" value="${settings.ticker_speed || 2.5}" min="0.5" max="10" step="0.5">
        </label>
        <h3>Ceas</h3>
        <label>Format ceas
          <select id="set-clock-format" class="input">
            <option value="HH:MM:SS" ${(settings.clock_format||'HH:MM:SS') === 'HH:MM:SS' ? 'selected' : ''}>HH:MM:SS</option>
            <option value="HH:MM" ${settings.clock_format === 'HH:MM' ? 'selected' : ''}>HH:MM</option>
          </select>
        </label>
        <h3>Cronometru</h3>
        <label>Durată implicită (sec)
          <input type="number" id="set-timer-default" class="input" value="${settings.timer_default || 60}" min="0">
        </label>
        <h3>Copyright</h3>
        <label><input type="checkbox" id="set-copyright-enabled" ${settings.copyright ? (() => { try { return JSON.parse(settings.copyright).enabled; } catch { return false; } })() ? 'checked' : '' : ''}> Activează copyright</label>
        <label>Mod
          <select id="set-copyright-mode" class="input">
            <option value="title_author">Titlu + Autor</option>
            <option value="title">Titlu</option>
            <option value="author">Autor</option>
            <option value="category">Categorie</option>
            <option value="source">Sursă</option>
            <option value="custom">Personalizat</option>
          </select>
        </label>
        <label>Text personalizat
          <input type="text" id="set-copyright-text" class="input" placeholder="Text copyright..." value="${settings.copyright ? (() => { try { return JSON.parse(settings.copyright).custom_text; } catch { return ''; } })() : ''}">
        </label>
        <label>Dimensiune font
          <input type="number" id="set-copyright-size" class="input" value="${settings.copyright ? (() => { try { return JSON.parse(settings.copyright).font_size; } catch { return 12; } })() : 12}" min="8" max="48">
        </label>
      </div>`;
  },

  tabWindows(settings, screens) {
    return `
      <div class="settings-section">
        <h3>Ferestre display</h3>
        <p style="color:#888;font-size:12px">Configurează ferestrele de afișare pentru fiecare ecran.</p>
        ${screens.map((s, i) => `
          <div class="window-config">
            <label><input type="checkbox" class="set-window-enabled" data-index="${i}" ${settings[`window_${i}_enabled`] !== 'false' ? 'checked' : ''}> Ecran ${i+1}: ${s.label}</label>
            <label>Nume
              <input type="text" class="set-window-name input" data-index="${i}" value="${settings[`window_${i}_name`] || s.label}">
            </label>
          </div>
        `).join('')}
      </div>`;
  },

  tabInterface(settings) {
    return `
      <div class="settings-section">
        <h3>Interfață</h3>
        <label>Limbă
          <select id="set-language" class="input">
            <option value="ro" ${(settings.language||'ro') === 'ro' ? 'selected' : ''}>Română</option>
            <option value="en" ${settings.language === 'en' ? 'selected' : ''}>English</option>
            <option value="de" ${settings.language === 'de' ? 'selected' : ''}>Deutsch</option>
            <option value="fr" ${settings.language === 'fr' ? 'selected' : ''}>Français</option>
            <option value="hu" ${settings.language === 'hu' ? 'selected' : ''}>Magyar</option>
          </select>
        </label>
        <label>Avans automat (secunde)
          <input type="number" id="set-auto-advance" class="input" value="${settings.autoAdvanceDelay || 5}" min="1" max="300">
        </label>
      </div>`;
  },

  tabCloud(settings) {
    return `
      <div class="settings-section">
        <h3>Supabase Cloud</h3>
        <label>URL
          <input type="text" id="set-supabase-url" class="input" value="${settings.supabase_url || ''}" placeholder="https://your-project.supabase.co">
        </label>
        <label>Cheie API
          <input type="password" id="set-supabase-key" class="input" value="${settings.supabase_key || ''}">
        </label>
        <div style="margin-top:8px">
          <button class="btn btn-sm btn-secondary" id="cloud-upload">☁ Încarcă datele</button>
          <button class="btn btn-sm btn-secondary" id="cloud-download">☁ Descarcă datele</button>
        </div>
      </div>`;
  },

  tabDatabase() {
    return `
      <div class="settings-section">
        <h3>Bază de date</h3>
        <p style="color:#888;font-size:12px">Operații de întreținere a bazei de date.</p>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
          <button class="btn btn-sm btn-secondary" id="db-reindex">🔄 Reindexare FTS</button>
          <button class="btn btn-sm btn-secondary" id="db-vacuum">🧹 Vacuum</button>
          <button class="btn btn-sm btn-secondary" id="db-check">🔍 Verificare integritate</button>
          <button class="btn btn-sm btn-secondary" id="db-export">📤 Export JSON</button>
          <button class="btn btn-sm btn-secondary" id="db-import">📥 Import JSON</button>
          <button class="btn btn-sm btn-secondary" id="db-open-folder">📂 Deschide folder</button>
        </div>
        <div id="db-result" style="margin-top:8px;color:#888;font-size:12px"></div>
      </div>`;
  },

  tabSecurity(settings, profiles, restrictions) {
    return `
      <div class="settings-section">
        <h3>Securitate profil</h3>
        <p style="color:#888;font-size:12px">Setări de securitate pentru profilul curent.</p>
        <label>Parolă profil
          <input type="password" id="set-profile-password" class="input" placeholder="Parolă nouă...">
        </label>
        <button class="btn btn-sm btn-primary" id="set-password-btn">Setează parola</button>
        <div style="margin-top:12px">
          <h4>Restricții</h4>
          <label><input type="checkbox" class="set-restriction" data-key="prevent_settings" ${restrictions.prevent_settings ? 'checked' : ''}> Preveni accesul la setări</label>
          <label><input type="checkbox" class="set-restriction" data-key="prevent_import" ${restrictions.prevent_import ? 'checked' : ''}> Preveni importul</label>
          <label><input type="checkbox" class="set-restriction" data-key="prevent_profile_change" ${restrictions.prevent_profile_change ? 'checked' : ''}> Preveni schimbarea profilului</label>
        </div>
      </div>`;
  },

  attachListeners(settings) {
    // Browse buttons
    document.getElementById('set-bg-image-browse')?.addEventListener('click', async () => {
      const r = await window.api.dialog.openFile({ filters: [{ name: 'Imagini', extensions: ['png','jpg','jpeg','gif','bmp','webp'] }] });
      if (!r.canceled && r.filePaths[0]) document.getElementById('set-bg-image').value = r.filePaths[0];
    });
    document.getElementById('set-bg-video-browse')?.addEventListener('click', async () => {
      const r = await window.api.dialog.openFile({ filters: [{ name: 'Video', extensions: ['mp4','avi','mov','mkv'] }] });
      if (!r.canceled && r.filePaths[0]) document.getElementById('set-bg-video').value = r.filePaths[0];
    });

    // DB operations
    document.getElementById('db-reindex')?.addEventListener('click', async () => {
      await DB.reindex();
      document.getElementById('db-result').textContent = '✓ Reindexare completă';
    });
    document.getElementById('db-vacuum')?.addEventListener('click', async () => {
      await DB.vacuum();
      document.getElementById('db-result').textContent = '✓ Vacuum complet';
    });
    document.getElementById('db-check')?.addEventListener('click', async () => {
      const r = await DB.checkIntegrity();
      document.getElementById('db-result').textContent = '✓ Integritate: ' + JSON.stringify(r);
    });
    document.getElementById('db-export')?.addEventListener('click', async () => {
      const r = await window.api.dialog.saveFile({ defaultPath: 'cantece.json', filters: [{ name: 'JSON', extensions: ['json'] }] });
      if (!r.canceled && r.filePath) {
        const json = await DB.songs.exportJson();
        require('fs').writeFileSync(r.filePath, json, 'utf-8');
        Utils.toast('Exportat cu succes', 'success');
      }
    });
    document.getElementById('db-import')?.addEventListener('click', async () => {
      const r = await window.api.dialog.openFile({ filters: [{ name: 'JSON', extensions: ['json'] }] });
      if (!r.canceled && r.filePaths[0]) {
        const fs = require('fs');
        const json = fs.readFileSync(r.filePaths[0], 'utf-8');
        const count = await DB.songs.importJson(json);
        Utils.toast(`${count} cântări importate`, 'success');
      }
    });
    document.getElementById('db-open-folder')?.addEventListener('click', () => {
      window.api.system.getInfo().then(info => window.api.system.openFolder(info.userData));
    });

    // Password
    document.getElementById('set-password-btn')?.addEventListener('click', async () => {
      const pwd = document.getElementById('set-profile-password')?.value || '';
      const profile = appState.get('profile');
      if (profile) {
        await window.api.db.profiles.setPassword(profile.name, pwd);
        Utils.toast(pwd ? 'Parolă setată' : 'Parolă ștearsă', 'success');
      }
    });

    // Restrictions
    document.querySelectorAll('.set-restriction').forEach(cb => {
      cb.addEventListener('change', async () => {
        const profile = appState.get('profile');
        if (profile) {
          await window.api.db.profiles.setRestriction(profile.name, cb.dataset.key, cb.checked);
        }
      });
    });

    // Cloud
    document.getElementById('cloud-upload')?.addEventListener('click', () => {
      Utils.toast('Cloud upload — în dezvoltare', 'info');
    });
    document.getElementById('cloud-download')?.addEventListener('click', () => {
      Utils.toast('Cloud download — în dezvoltare', 'info');
    });
  },

  async save(settings) {
    const getVal = (id, def) => (document.getElementById(id)?.value ?? def);
    const getBool = (id) => document.getElementById(id)?.checked ?? false;

    settings.bg_color = getVal('set-bg-color', '#000000');
    settings.bg_image = getVal('set-bg-image', '');
    settings.bg_video = getVal('set-bg-video', '');
    settings.transition = getVal('set-transition', 'crossfade');
    settings.transition_duration = parseInt(getVal('set-transition-duration', '350'));
    settings.font_family = getVal('set-font-family', 'Arial');
    settings.font_size = parseInt(getVal('set-font-size', '48'));
    settings.text_color = getVal('set-text-color', '#ffffff');
    settings.outline_color = getVal('set-outline-color', '#000000');
    settings.outline_width = parseInt(getVal('set-outline-width', '2'));
    settings.text_shadow = getBool('set-text-shadow') ? 'true' : 'false';
    settings.font_bold = getBool('set-font-bold') ? 'true' : 'false';
    settings.font_italic = getBool('set-font-italic') ? 'true' : 'false';
    settings.text_align = getVal('set-text-align', 'center');
    settings.text_valign = getVal('set-text-valign', 'center');
    settings.margin = parseInt(getVal('set-margin', '80'));
    settings.line_spacing = parseFloat(getVal('set-line-spacing', '1.4'));
    settings.sacred_words = getVal('set-sacred-words', '');
    settings.sacred_words_enabled = getBool('set-sacred-enabled') ? 'true' : 'false';
    settings.language = getVal('set-language', 'ro');
    settings.autoAdvanceDelay = parseInt(getVal('set-auto-advance', '5'));
    settings.supabase_url = getVal('set-supabase-url', '');
    settings.supabase_key = getVal('set-supabase-key', '');
    settings.ticker_speed = parseFloat(getVal('set-ticker-speed', '2.5'));
    settings.clock_format = getVal('set-clock-format', 'HH:MM:SS');
    settings.timer_default = parseInt(getVal('set-timer-default', '60'));

    // Copyright
    const crEnabled = getBool('set-copyright-enabled');
    const crMode = getVal('set-copyright-mode', 'title_author');
    const crText = getVal('set-copyright-text', '');
    const crSize = parseInt(getVal('set-copyright-size', '12'));
    settings.copyright = JSON.stringify({
      enabled: crEnabled, mode: crMode, custom_text: crText,
      position: 'bottom_right', color: '#ffffff', opacity: 0.4, font_size: crSize,
    });

    const merged = await window.api.settings.set(settings);
    appState.setSettings(merged);
    Utils.toast('Setări salvate', 'success');

    // Close dialog
    const overlay = document.getElementById('dialog-overlay');
    if (overlay) overlay.classList.remove('dialog-active');
  },
};
