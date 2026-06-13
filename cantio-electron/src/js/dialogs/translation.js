Dialogs = Dialogs || {};
Dialogs.translation = {
  async open(slides) {
    if (!slides || slides.length < 2) {
      Utils.toast('Selectează cel puțin 2 slide-uri pentru traducere', 'warning');
      return;
    }

    const html = `
      <div class="translation-dialog">
        <h2>Traducere duală Biblia</h2>
        <p style="color:#888;font-size:12px;margin-bottom:8px">Aranjează slide-urile pentru afișare față în față.</p>
        <div class="translation-layout">
          <div class="translation-panel">
            <h4>Stânga</h4>
            <select id="trans-left" class="input" size="6">
              ${slides.map((s, i) => `<option value="${i}">${i+1}: ${(s.text||s).slice(0,60)}</option>`).join('')}
            </select>
          </div>
          <div class="translation-panel">
            <h4>Dreapta</h4>
            <select id="trans-right" class="input" size="6">
              ${slides.map((s, i) => `<option value="${i + slides.length}">${i+1}: ${(s.text||s).slice(0,60)}</option>`).join('')}
            </select>
          </div>
        </div>
        <div class="dialog-buttons">
          <button class="btn btn-secondary" data-close="close">Anulează</button>
          <button class="btn btn-primary" id="trans-apply">Aplică aranjament</button>
        </div>
      </div>`;

    Utils.dialog(html, 600).then(() => {});

    document.getElementById('trans-apply')?.addEventListener('click', () => {
      const left = document.getElementById('trans-left');
      const right = document.getElementById('trans-right');
      if (!left || !right) return;
      const leftIdx = parseInt(left.value);
      const rightIdx = parseInt(right.value);
      if (isNaN(leftIdx) || isNaN(rightIdx)) {
        Utils.toast('Selectează câte un slide din fiecare panou', 'warning'); return;
      }

      const leftSlide = typeof slides[leftIdx] === 'object' ? slides[leftIdx] : { text: slides[leftIdx] };
      const rightSlide = typeof slides[rightIdx - slides.length] === 'object' ? slides[rightIdx - slides.length] : { text: slides[rightIdx - slides.length] };

      const combined = [
        { text: leftSlide.text || '', translation: rightSlide.text || '', metadata: { dualLanguage: true } }
      ];

      appState.setSlides(combined);
      window.App.goLive();
      Utils.toast('Aranjament aplicat', 'success');

      const overlay = document.getElementById('dialog-overlay');
      if (overlay) overlay.classList.remove('dialog-active');
    });
  },
};
