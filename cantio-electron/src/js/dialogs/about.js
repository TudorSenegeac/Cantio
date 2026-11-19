Dialogs = Dialogs || {};
Dialogs.about = {
  async open() {
    let info = {};
    try {
      const sysInfo = await window.api.system.getInfo();
      info = sysInfo || {};
    } catch {}

    const pkg = {};
    try {
      const fs = require('fs');
      const pkgPath = require('path').join(__dirname, '..', '..', 'package.json');
      if (fs.existsSync(pkgPath)) {
        Object.assign(pkg, JSON.parse(fs.readFileSync(pkgPath, 'utf-8')));
      }
    } catch {}

    const html = `
      <div class="about-dialog">
        <h2>Despre Cantio</h2>
        <div class="about-logo">
          <div class="logo-placeholder">C</div>
        </div>
        <table class="about-table">
          <tr><td>Aplicație</td><td>${pkg.name || 'Cantio Electron'}</td></tr>
          <tr><td>Versiune</td><td>${pkg.version || '1.0.0'}</td></tr>
          <tr><td>Electron</td><td>${info.electron || 'N/A'}</td></tr>
          <tr><td>Node.js</td><td>${info.node || 'N/A'}</td></tr>
          <tr><td>Chrome</td><td>${info.chrome || 'N/A'}</td></tr>
          <tr><td>Platformă</td><td>${info.platform || 'N/A'}</td></tr>
          <tr><td>Profil curent</td><td>${(appState.get('profile') || {}).name || 'N/A'}</td></tr>
        </table>
        <p style="color:#888;font-size:12px;text-align:center;margin-top:8px">
          Software pentru managementul închinării. Licență GPL v3.
        </p>
        <div class="dialog-buttons">
          <button class="btn btn-secondary" data-close="close">Închide</button>
        </div>
      </div>`;

    Utils.dialog(html, 400).then(() => {});
  },
};
