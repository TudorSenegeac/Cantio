Dialogs = Dialogs || {};
Dialogs.profile = {
  async open() {
    const profiles = await window.api.db.profiles.list();
    const currentProfile = appState.get('profile');

    const html = `
      <div class="profile-dialog">
        <h2>Profil</h2>
        <div style="margin-bottom:12px">
          <input type="text" id="profile-new-name" class="input" placeholder="Nume profil nou...">
        </div>
        <div style="margin-bottom:12px">
          <button class="btn btn-sm btn-primary" id="profile-create">+ Crează profil</button>
        </div>
        <div id="profile-list">
          ${profiles.map(p => `
            <div class="profile-item ${currentProfile && currentProfile.name === p.name ? 'active' : ''}" data-profile="${p.name}">
              <span class="profile-name">${p.name}</span>
              <div class="profile-actions">
                <button class="btn btn-sm btn-secondary profile-rename" data-profile="${p.name}">✏️</button>
                <button class="btn btn-sm btn-secondary profile-password" data-profile="${p.name}">🔒</button>
                <button class="btn btn-sm btn-danger profile-delete" data-profile="${p.name}">🗑</button>
              </div>
            </div>
          `).join('')}
        </div>
        ${currentProfile ? `
          <div class="dialog-buttons" style="margin-top:12px">
            <button class="btn btn-secondary" data-close="close">Închide</button>
            ${currentProfile.restrictions && currentProfile.restrictions.prevent_profile_change ? '' : `
              <button class="btn btn-danger" id="profile-delete-current">Șterge profilul curent</button>
            `}
          </div>
        ` : `
          <div class="dialog-buttons" style="margin-top:12px">
            <button class="btn btn-secondary" data-close="close">Închide</button>
          </div>
        `}
      </div>`;

    Utils.dialog(html, 450).then(() => {});

    document.getElementById('profile-create')?.addEventListener('click', async () => {
      const name = document.getElementById('profile-new-name')?.value?.trim();
      if (!name) { Utils.toast('Introdu un nume', 'warning'); return; }
      try {
        await window.api.db.profiles.create(name);
        Utils.toast(`Profil "${name}" creat`, 'success');
        this.open(); // Refresh
      } catch (e) {
        Utils.toast('Eroare: ' + e.message, 'error');
      }
    });

    document.querySelectorAll('.profile-rename').forEach(btn => {
      btn.addEventListener('click', async () => {
        const oldName = btn.dataset.profile;
        const newName = prompt('Nume nou:', oldName);
        if (newName && newName !== oldName) {
          await window.api.db.profiles.rename(oldName, newName);
          Utils.toast(`Profil redenumit în "${newName}"`, 'success');
          this.open();
        }
      });
    });

    document.querySelectorAll('.profile-password').forEach(btn => {
      btn.addEventListener('click', async () => {
        const name = btn.dataset.profile;
        const pwd = prompt('Parolă nouă (lasă gol pentru a șterge):');
        if (pwd !== null) {
          await window.api.db.profiles.setPassword(name, pwd);
          Utils.toast(pwd ? 'Parolă setată' : 'Parolă ștearsă', 'success');
        }
      });
    });

    document.querySelectorAll('.profile-delete').forEach(btn => {
      btn.addEventListener('click', async () => {
        const name = btn.dataset.profile;
        if (!confirm(`Sigur ștergi profilul "${name}"?`)) return;
        await window.api.db.profiles.delete(name);
        Utils.toast(`Profil "${name}" șters`, 'success');
        this.open();
      });
    });

    document.getElementById('profile-delete-current')?.addEventListener('click', async () => {
      const profile = currentProfile;
      if (!profile || !confirm(`Sigur ștergi profilul curent "${profile.name}"?`)) return;
      await window.api.db.profiles.delete(profile.name);
      Utils.toast(`Profil "${profile.name}" șters`, 'success');
      const overlay = document.getElementById('dialog-overlay');
      if (overlay) overlay.classList.remove('dialog-active');
    });
  },
};
