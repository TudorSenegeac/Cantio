# Campanie 1.6.0 — „fără bug-uri" (urmărire)

> Scop: CantioPresenter 1.6.0 — testat complet, feature cu feature, bug-urile reproduse pe viu,
> reparate și re-testate. Nu promitem zero absolut (imposibil la orice software), dar facem o
> trecere sistematică reală. Fiecare bug: **reprodus → cauză → fix (commit) → re-testat**.

Legendă stare: 🔴 raportat/nec.confirmat · 🟡 reprodus, în lucru · 🟢 reparat+testat · ⚪ nu s-a putut reproduce

---

## A. Bug-uri raportate de user (14 nov 2026)

### A1 🟡 Fundal greșit la cântare (albastru în loc de zăpadă) — CAUZĂ CONFIRMATĂ
- **Simptom (user):** „pun o cântare, textul are fontul temei default, dar fundalul e unul albastru
  deși era unul cu zăpadă".
- **CAUZĂ (confirmată din date + cod):** cântarea are un **proiect „editor avansat"** salvat
  (`~/Cantio/song_slides/{id}__{look}.json`, ex. `22748__craciunnn.json`). La go-live,
  `control_window._go_live` (l.10212-10214) face:
  ```python
  _rich = self._send_rich_slide_live(idx)
  if not _rich:
      self._apply_custom_bg_from_settings(_live_settings)  # fundalul temei (zăpadă) se trimite DOAR aici
  ```
  Când proiectul rich există, `_send_rich_slide_live` returnează True → fundalul temei e SĂRIT.
  Proiectul rich își desenează propriul strat `gradient` (albastru `#1a1a5a`/`#5294e2`) + text
  (overlay cu fontul temei). Rezultat: **text cu fontul temei + fundal albastru, fără zăpadă** — exact simptomul.
- **Agravant:** `_rich_project_path` (l.9239-9247) **auto-migrează** un proiect vechi `{id}.json`
  pe ORICE look nou selectat (`shutil.copy2(legacy, {id}__{look}.json)`), deci un design vechi de test
  îngheață fundalul și pe look-uri la care userul nu l-a editat niciodată.
- **Blast radius:** cântări cu proiect rich: 13638, 14138, 21345, 22742, 22748, 22749–22752, 4, 8, 634,
  „Cantare" (majoritatea cântări de test). Toate au strat bg propriu → suprascriu tema.
- **CLUSTER (confirmat de audit static, complementar):**
  - **A1b:** `_apply_current_song_theme_live` (l.5791-5803) la schimbarea temei/look pe cântare trimite
    DOAR `apply_settings` (font/text), niciodată `_apply_custom_bg_from_settings`/`show_background` →
    fundalul temei (zăpadă) nu ajunge pe output; rămâne fundalul vechi. (Preview-ul îl trimite corect
    via `_push_preview` → de-aia preview arată zăpadă, proiectorul nu.) **Fix:** după `dw.apply_settings(s)`
    adaugă `self._apply_custom_bg_from_settings(s)`.
  - **A1c (de ce e ALBASTRU, nu negru):** `_theme_to_settings` ramurile ne-gradient (fundal/image/video/color)
    NU curăță `bg_grad_c1/c2` moștenite din global → când fundalul se pierde, apar culorile gradient vechi
    (#000033). **Fix:** golește `bg_grad_c1/c2` în ramurile ne-gradient.
  - **A1d (robustețe rename/profil):** `_apply_custom_bg_from_settings`/`_resolve_preview_bg` abandonează în
    tăcere dacă `os.path.exists(fundal_file)` e False (cale absolută spre alt profil/după redenumire).
    **Fix:** dacă lipsește, caută basename-ul în `_bg_fundal_dir()` curent înainte de a renunța.
  - **A1e (latent):** Look global activ (`active_look`) are Prioritate 0 în `_resolve_settings` (l.9797) și
    acoperă tema per-cântare. Acum `active_look=''`, deci inactiv — dar de reținut.
- **A1a — DECIS de user: „TEMA CÂȘTIGĂ".** Fix aplicat: `_send_rich_slide_live` primește settings-urile
  rezolvate; dacă `bg_type ∈ {fundal,image,video}` → `return False` (designul avansat NU se aplică, tema
  câștigă; text ca overlay normal). Designul avansat rămâne activ doar când tema are fundal simplu
  (culoare/gradient). Ambii apelanți pasează `_live_settings`. Asta repară RETROACTIV și cazul existent
  (`22748__craciunnn.json`) fără să ștergem nimic.
- **A1 (auto-migrare):** `_rich_project_path` migrează legacy→look DOAR la `for_create=True` (deschiderea
  explicită a editorului avansat), nu la afișare → nu se mai propagă design-uri vechi pe look-uri noi.
- **TOATE fixurile A1 (a/b/c/d) aplicate. Compile OK.** Stare: 🟢 reparat în cod — **de verificat pe viu**.

### A2 ⚪ Biblie — lipsesc spații între cuvinte — NU AM PUTUT REPRODUCE
- **Simptom (user):** „nici la Biblie nu e ok, nu lasă unele spații între cuvinte".
- **Ipoteza inițială (audit):** `drawStyledText` folosea `measureText(run)` care ar tăia spațiul de la
  coadă → spațiul dinaintea cuvântului evidențiat dispare. **INFIRMATĂ EMPIRIC:**
  - Test canvas în browser (Chromium nou): vechi și nou randează identic, cu spațiu. gap=0.
  - Test `measureText` în **Electron 28 (Chromium ~120, randorul REAL al aplicației)**: gap=0,
    `measure('For God so ')−measure('For God so')` = 12.78px → spațiul de la coadă E numărat corect.
  - Deci fixul `_advW` era un **no-op** → l-am dat înapoi (display.js = neschimbat).
- **Testat pe viu în aplicație (profil Cantio, Ioan 3:16):**
  - Verset simplu: toate spațiile corecte (preview Qt).
  - Verset cu evidențiere: toate spațiile corecte; (evidențierea nu apare în preview-ul Qt pt. că
    preview_widget STRIPEAZĂ marcajele — limitare cunoscută; pe proiectorul real apare colorat).
- **CONCLUZIE:** nu reproduc lipsa de spații în niciun randor. Posibil deja reparat, sau un scenariu
  specific (altă traducere/verset). **NEVOIE de un exemplu concret de la user** (ce verset, ce traducere,
  cu/ fără evidențiere, ideal o poză a ecranului).
- **Stare:** neconfirmat/neprodus; aștept exemplu concret.

### A3 🔴 Fundalurile animate — „nu au nicio eroare" (de verificat ce a vrut să zică)
- **Notă:** formulare neclară în mesaj. De clarificat la testare dacă e „nu merg / nu se animă"
  sau „nu dau eroare dar arată greșit". De observat pe viu.

---

## B. Bug-uri găsite de audit (static) — de confirmat

### B1 🔴 Evidențiere Biblie — se marchează ocurența greșită
- `bible_control_tab.py:413` folosește `base.find(sel)` → prima ocurență; o selecție scurtă poate
  nimeri un cuvânt anterior sau un substring din alt cuvânt (ex. „so" în „Also"). Nu pierde spațiu,
  dar evidențiază caracterele greșite. **Fix:** folosește `cursor.selectionStart()` în loc de `find()`.
- **Stare:** de reparat (fix fiabil necesită maparea indicilor U+2029↔\n + strip; low-priority).

### B3 🟡 Evidențierea NU apare în preview-ul operatorului (Qt)
- `preview_widget` stripează marcajele `[[h:..]]` → operatorul NU vede evidențierea în preview, doar pe
  proiector. Confuz la operare. Opțiune: randează marcajele și în preview-ul Qt (convertește la HTML
  `<span>` / culoare). **Stare:** de evaluat.

### B2 🔴 A1e — Look global acoperă tema per-cântare (latent)
- `_resolve_settings:9797` Prioritate 0: un `active_look` setat se aplică la ORICE cântare, ignorând
  tema per-cântare (deci și fundalul ei). Acum `active_look=''`. De verificat că resetarea look-ului
  e mereu posibilă/evidentă.

---

## Fixuri aplicate în această sesiune — doar `control_window.py` (display.js = NESCHIMBAT)
- **A1a** (tema câștigă peste designul avansat) — `_send_rich_slide_live` returnează False când
  `bg_type ∈ {fundal,image,video}`; ambii apelanți pasează `_live_settings`.
- **A1b** (schimbarea temei/look trimite și fundalul) — `_apply_current_song_theme_live`.
- **A1c** (golește culorile gradient vechi la fundal ne-gradient) — `_theme_to_settings`.
- **A1d** (cale fundal robustă la profil/redenumire) — `_resolve_fundal_path` + 2 call-site-uri.
- **A1 auto-migrare** — `_rich_project_path` migrează legacy→look doar la `for_create=True`.
- **VERIFICAT PE VIU:** motorul real `bg-engine.js` randează `crăciun.json` = negru + fulgi albi (nu
  albastru). Resolution logic trasată din date+cod. A1 = 🟢 confirmat.
- A2: fixul `_advW` a fost **dat înapoi** (no-op dovedit). display.js identic cu originalul.
- Compile-check: `py_compile control_window.py` OK, `node --check display.js` OK.

---

## C. Bug-uri găsite la testarea pe viu

(se completează pe măsură ce testez feature cu feature)

---

## Istoric reparări
(commit-uri pe măsură ce reparăm)
