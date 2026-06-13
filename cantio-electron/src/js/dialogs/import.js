Dialogs = Dialogs || {};
Dialogs.import = {
  async open() {
    const html = `
      <div class="import-dialog">
        <h2>Importă</h2>
        <div class="settings-tabs">
          <button class="settings-tab active" data-itab="cantece">Cântări</button>
          <button class="settings-tab" data-itab="biblia">Biblia</button>
          <button class="settings-tab" data-itab="serviciu">Serviciu</button>
        </div>
        <div id="import-content" class="settings-content">
          ${this.tabSongs()}
        </div>
        <div id="import-progress" style="display:none;margin-top:8px">
          <div class="progress-bar"><div id="import-progress-bar" class="progress-fill" style="width:0%"></div></div>
          <p id="import-status" style="font-size:12px;color:#888;margin-top:4px"></p>
        </div>
        <div class="dialog-buttons">
          <button class="btn btn-secondary" data-close="close">Închide</button>
        </div>
      </div>`;

    Utils.dialog(html, 550).then(() => {});

    document.querySelectorAll('[data-itab]').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('[data-itab]').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const section = tab.dataset.itab;
        const content = document.getElementById('import-content');
        if (content) {
          switch (section) {
            case 'cantece': content.innerHTML = this.tabSongs(); break;
            case 'biblia': content.innerHTML = this.tabBible(); break;
            case 'serviciu': content.innerHTML = this.tabService(); break;
          }
          this.attachListeners();
        }
      });
    });

    setTimeout(() => this.attachListeners(), 100);
  },

  tabSongs() {
    return `
      <div class="settings-section">
        <h3>Importă cântări</h3>
        <label>Fișier
          <input type="text" id="import-file-path" class="input" placeholder="Selectează fișier...">
          <button class="btn btn-sm btn-secondary" id="import-file-browse">📁</button>
        </label>
        <div class="import-options" style="margin-top:8px">
          <button class="btn btn-sm btn-primary" id="import-start">📥 Importă</button>
        </div>
        <h4 style="margin-top:12px">Importă folder</h4>
        <label>Folder
          <input type="text" id="import-folder-path" class="input" placeholder="Selectează folder...">
          <button class="btn btn-sm btn-secondary" id="import-folder-browse">📁</button>
        </label>
        <div style="margin-top:8px">
          <button class="btn btn-sm btn-primary" id="import-folder-start">📥 Importă folder</button>
        </div>
        <div id="import-history" style="margin-top:12px">
          <h4>Istoric importuri</h4>
          <div id="import-history-list"><p style="color:#888;font-size:12px">Încărcare...</p></div>
        </div>
      </div>`;
  },

  tabBible() {
    return `
      <div class="settings-section">
        <h3>Importă traducere Biblie</h3>
        <label>Fișier
          <input type="text" id="import-bible-file" class="input" placeholder="Selectează fișier USFX/OSIS/JSON...">
          <button class="btn btn-sm btn-secondary" id="import-bible-browse">📁</button>
        </label>
        <label>Nume traducere
          <input type="text" id="import-bible-name" class="input" placeholder="ex: NTR, VDC, KJV">
        </label>
        <label>Limbă
          <select id="import-bible-lang" class="input">
            <option value="ro">Română</option>
            <option value="en">English</option>
            <option value="de">Deutsch</option>
            <option value="fr">Français</option>
            <option value="hu">Magyar</option>
          </select>
        </label>
        <div style="margin-top:8px">
          <button class="btn btn-sm btn-primary" id="import-bible-start">📥 Importă traducerea</button>
        </div>
      </div>`;
  },

  tabService() {
    return `
      <div class="settings-section">
        <h3>Importă serviciu</h3>
        <label>Fișier GPS (serviciu)
          <input type="text" id="import-service-file" class="input" placeholder="Selectează fișier .gps...">
          <button class="btn btn-sm btn-secondary" id="import-service-browse">📁</button>
        </label>
        <div style="margin-top:8px">
          <button class="btn btn-sm btn-primary" id="import-service-start">📥 Importă serviciu</button>
        </div>
      </div>`;
  },

  attachListeners() {
    document.getElementById('import-file-browse')?.addEventListener('click', async () => {
      const r = await window.api.dialog.openFile({ title: 'Selectează fișier', filters: [
        { name: 'Cântări', extensions: ['txt','json','xml','vpc','ewsx','docx'] },
      ]});
      if (!r.canceled && r.filePaths[0]) document.getElementById('import-file-path').value = r.filePaths[0];
    });

    document.getElementById('import-folder-browse')?.addEventListener('click', async () => {
      const r = await window.api.dialog.openFolder({ title: 'Selectează folder' });
      if (!r.canceled && r.filePaths[0]) document.getElementById('import-folder-path').value = r.filePaths[0];
    });

    document.getElementById('import-bible-browse')?.addEventListener('click', async () => {
      const r = await window.api.dialog.openFile({ filters: [{ name: 'Bible', extensions: ['usfx','xml','osis','json'] }] });
      if (!r.canceled && r.filePaths[0]) document.getElementById('import-bible-file').value = r.filePaths[0];
    });

    document.getElementById('import-service-browse')?.addEventListener('click', async () => {
      const r = await window.api.dialog.openFile({ filters: [{ name: 'GPS Service', extensions: ['gps'] }] });
      if (!r.canceled && r.filePaths[0]) document.getElementById('import-service-file').value = r.filePaths[0];
    });

    document.getElementById('import-start')?.addEventListener('click', () => this.doImportFile());
    document.getElementById('import-folder-start')?.addEventListener('click', () => this.doImportFolder());
    document.getElementById('import-bible-start')?.addEventListener('click', () => this.doImportBible());
    document.getElementById('import-service-start')?.addEventListener('click', () => this.doImportService());

    this.loadHistory();
  },

  async loadHistory() {
    const el = document.getElementById('import-history-list');
    if (!el) return;
    try {
      const history = await DB.settings.get('import_history') || '[]';
      const items = JSON.parse(history);
      if (!items.length) { el.innerHTML = '<p style="color:#888;font-size:12px">Niciun import anterior</p>'; return; }
      el.innerHTML = items.slice(-10).reverse().map(i =>
        `<div class="history-item">${i.file || i.source || 'Necunoscut'} — ${i.count || 0} cântece (${i.date || ''})</div>`
      ).join('');
    } catch { el.innerHTML = '<p style="color:#888;font-size:12px">Eroare încărcare istoric</p>'; }
  },

  async doImportFile() {
    const filePath = document.getElementById('import-file-path')?.value;
    if (!filePath) { Utils.toast('Selectează un fișier', 'warning'); return; }
    this.showProgress(true);
    try {
      const result = await window.api.import.file(filePath);
      this.showProgress(false);
      if (result.success) {
        Utils.toast(`${result.count} cânteci importate`, 'success');
        await this.recordHistory(filePath, result.count);
        this.loadHistory();
      } else {
        Utils.toast(result.error || 'Eroare import', 'error');
      }
    } catch (e) {
      this.showProgress(false);
      Utils.toast('Eroare: ' + e.message, 'error');
    }
  },

  async doImportFolder() {
    const folderPath = document.getElementById('import-folder-path')?.value;
    if (!folderPath) { Utils.toast('Selectează un folder', 'warning'); return; }
    this.showProgress(true);
    try {
      const result = await window.api.import.folder(folderPath);
      this.showProgress(false);
      if (result.success) {
        Utils.toast(`${result.count} cânteci importate`, 'success');
        this.loadHistory();
      } else {
        Utils.toast(result.error || 'Eroare import folder', 'error');
      }
    } catch (e) {
      this.showProgress(false);
      Utils.toast('Eroare: ' + e.message, 'error');
    }
  },

  async doImportBible() {
    const filePath = document.getElementById('import-bible-file')?.value;
    const name = document.getElementById('import-bible-name')?.value;
    const lang = document.getElementById('import-bible-lang')?.value;
    if (!filePath || !name) { Utils.toast('Completează toate câmpurile', 'warning'); return; }
    this.showProgress(true);
    try {
      const result = await window.api.import.bible(filePath, name, lang);
      this.showProgress(false);
      if (result.success) {
        Utils.toast(`Traducerea "${name}" importată (${result.verses} versete)`, 'success');
      } else {
        Utils.toast(result.error || 'Eroare import traducere', 'error');
      }
    } catch (e) {
      this.showProgress(false);
      Utils.toast('Eroare: ' + e.message, 'error');
    }
  },

  async doImportService() {
    const filePath = document.getElementById('import-service-file')?.value;
    if (!filePath) { Utils.toast('Selectează un fișier .gps', 'warning'); return; }
    this.showProgress(true);
    try {
      const result = await window.api.import.serviceGps(filePath);
      this.showProgress(false);
      if (result.success) {
        Utils.toast('Serviciu importat', 'success');
      } else {
        Utils.toast(result.error || 'Eroare import serviciu', 'error');
      }
    } catch (e) {
      this.showProgress(false);
      Utils.toast('Eroare: ' + e.message, 'error');
    }
  },

  async recordHistory(file, count) {
    const history = JSON.parse(await DB.settings.get('import_history') || '[]');
    history.push({ file, count, date: new Date().toISOString().slice(0, 10) });
    await DB.settings.set('import_history', JSON.stringify(history));
  },

  showProgress(show) {
    const el = document.getElementById('import-progress');
    const bar = document.getElementById('import-progress-bar');
    const status = document.getElementById('import-status');
    if (el) el.style.display = show ? 'block' : 'none';
    if (bar) bar.style.width = show ? '30%' : '0%';
    if (status) status.textContent = show ? 'Importare în curs...' : '';
  },
};
