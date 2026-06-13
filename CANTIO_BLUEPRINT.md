# CANTIO — BLUEPRINT COMPLET AL APLICAȚIEI

> Document tehnic de referință scris în totalitate în limba română.
> Acoperă toate subsistemele, valorile exacte, comportamentele și regulile de afișare.
> Versiune documentată: Cantio 1.0.0

---

## CUPRINS

1. Prezentare generală și arhitectură
2. Structura fișierelor și directoarelor
3. Baza de date — schema, indecși, migrare
4. Sistemul de profiluri și securitate
5. Fereastra principală de control (operator)
6. Biblioteca de cântări — căutare, afișare, editare
7. Lista de serviciu (playlist)
8. Editorul de slide-uri și miniaturi
9. Motorul de afișare Electron (fereastra live)
10. Randarea textului pe ecranul de proiecție
11. Fundal — tipuri, tranziții, video, cameră
12. Overlay-uri — Ticker, Ceas, Timer
13. Modulul Biblie
14. Teme vizuale — editor, carduri, previzualizare
15. Setări — fereastră, câmpuri, valori implicite
16. Server web pentru control de la distanță (mobil)
17. Monitor de scenă (Stage Monitor)
18. Import și export — formate suportate
19. Traducere automată a cântărilor
20. Editor de prezentări grafice
21. Modulul media — fișiere locale, camere, cloud
22. Notificări, jurnal și utilitare interne
23. Pornire, inițializare și ciclu de viață al aplicației

---

## 1. PREZENTARE GENERALĂ ȘI ARHITECTURĂ

### 1.1 Ce este Cantio

Cantio este un software de prezentare destinat serviciilor religioase (biserici, coruri, conferințe creștine). Permite operatorului să caute cântări, să le organizeze într-un serviciu, să trimită versuri pe ecranul de proiecție în timp real și să controleze tot din fereastra de operator, fără a întrerupe afișajul.

Aplicația rulează pe Windows, macOS și Linux. Interfața de operator este construită cu PyQt6 (Python), iar ecranul de proiecție este gestionat de un proces Electron separat (Node.js). Cele două procese comunică prin WebSocket pe portul local 7432.

### 1.2 Arhitectura de ansamblu

```
┌─────────────────────────────────────────────────┐
│        FEREASTRA DE OPERATOR (PyQt6 / Python)   │
│  • Biblioteca de cântări                        │
│  • Lista de serviciu                            │
│  • Editor slide-uri                             │
│  • Preview live (320×180 px, 15 fps)            │
│  • Setări, Teme, Biblie, Media                  │
└───────────────────┬────────────────┬────────────┘
                    │                │
         WebSocket  │  port 7432     │  Flask/SocketIO
         (Electron) │                │  port 5050
                    ▼                ▼
         ┌──────────────┐   ┌────────────────────┐
         │ ELECTRON     │   │ SERVER WEB MOBIL   │
         │ (display.js) │   │ (remote_server.py) │
         │ Ecran HDMI 2 │   │ Browser telefon    │
         └──────────────┘   └────────────────────┘
```

### 1.3 Tehnologii utilizate

| Componentă | Tehnologie | Scop |
|---|---|---|
| Interfața operator | PyQt6 (Python 3.10+) | UI desktop |
| Ecranul de proiecție | Electron + Node.js | Fereastră fullscreen |
| Baza de date | SQLite 3 (WAL, FTS5) | Cântări, Biblie, setări |
| Comunicare intern | WebSocket (port 7432) | Python ↔ Electron |
| Control mobil | Flask + SocketIO (port 5050) | Telefon/tabletă → operator |
| Video fundal | OpenCV (cv2) | Decodare frame-uri video |
| Cloud media | GitHub API (cantio-media repo) | Fișiere media online |
| Import PDF | PyMuPDF (fitz) | Extragere text din PDF |
| Import DOCX | python-docx | Extragere text din Word |
| Traducere | deep-translator (GoogleTranslator) | Traducere automată versuri |
| Cod QR | qrcode (Python) | QR pentru controlul mobil |

### 1.4 Fluxul principal de lucru

1. Operatorul pornește Cantio → apare ecranul de pornire (splash) → se alege profilul.
2. Se deschide fereastra de operator. Ecranul de proiecție (Electron) nu pornește automat.
3. Operatorul caută o cântare în bibliotecă, o adaugă la lista de serviciu.
4. Deschide ecranul de proiecție cu butonul „Deschide ecran" (sau F11).
5. Dă click pe un slide din panoul de slide-uri → versurile apar pe ecranul de proiecție.
6. Navigarea între slide-uri se face cu săgeți (←/→) sau click direct pe miniatură.
7. La final, operatorul trimite ecran negru sau oprește proiectorul.

---

## 2. STRUCTURA FIȘIERELOR ȘI DIRECTOARELOR

### 2.1 Directorul de date al aplicației

Locația directorului de date variază în funcție de sistemul de operare:

- **Windows**: `C:\Users\<utilizator>\Cantio\`
- **macOS**: `~/Library/Application Support/Cantio/`
- **Linux**: `~/.local/share/Cantio/`

Dacă există un director vechi `GlorifyPro` în aceeași locație, fișierele sunt migrate automat.

### 2.2 Structura directoarelor de date

```
~/Cantio/
├── profiles/
│   ├── default/
│   │   ├── cantio.db          ← baza de date SQLite (cântări + setări)
│   │   ├── bible.db           ← baza de date Biblie (opțional)
│   │   ├── settings.json      ← setările temei curente
│   │   ├── playlists.json     ← playlisturi salvate
│   │   ├── presentations.json ← prezentări grafice
│   │   ├── stage.json         ← layout monitor de scenă
│   │   └── cache.json         ← cache intern
│   ├── <alt-profil>/
│   │   └── ...
│   └── profile_config.json    ← parola și restricțiile profilului
├── logs/
│   └── cantio_YYYYMMDD.log    ← jurnale zilnice (max 7 păstrate)
├── media_cache/               ← cache fișiere media descărcate din cloud
├── recent_services.json       ← ultimele 5 servicii deschise
└── import_history.json        ← istoricul ultimelor 50 importuri
```

### 2.3 Fișierele sursă Python

Toate fișierele sursă Python se află direct în directorul aplicației (ex. `C:\Cantio\`):

| Fișier | Rol |
|---|---|
| `main.py` | Punct de intrare, pornire aplicație |
| `control_window.py` | Fereastra principală de operator |
| `database.py` | Toate operațiunile cu baza de date |
| `translations.py` | Textele interfeței în 5 limbi |
| `electron_display.py` | Manager comunicare cu procesul Electron |
| `display_window.py` | Fereastra de afișare PyQt (alternativă locală) |
| `renderer.py` | Motor de randare text/fundal (comun) |
| `render_engine.py` | Randare pe fir separat (preview + display) |
| `preview_widget.py` | Widgetul de previzualizare 320×180 |
| `live_state.py` | Starea live centralizată (singleton) |
| `settings_dialog.py` | Dialog setări temă |
| `theme_editor.py` | Editor vizual de teme |
| `themes_tab.py` | Tab-ul Teme din interfața principală |
| `bible_control_tab.py` | Tab-ul Biblie (panou control) |
| `bible_panel.py` | Shim de compatibilitate → bible_control_tab |
| `service_manager.py` | Salvare/încărcare fișiere serviciu (.gps) |
| `import_manager.py` | Manager import cântări (fir de execuție) |
| `importer.py` | Parsere formate: TXT, DOCX, PDF, VideoPsalm |
| `profile_manager.py` | Gestionare profiluri utilizatori |
| `keyboard_shortcuts.py` | Definirea și afișarea scurtăturilor |
| `toast_notifications.py` | Notificări pop-up non-blocante |
| `remote_server.py` | Server web mobil (Flask) |
| `stage_monitor.py` | Monitorul de scenă |
| `cloud_manager.py` | Integrare Supabase (cloud media) |
| `media_tab.py` | Tab-ul Media (locale, camere, cloud) |
| `overlay_tab.py` | Tab-ul Overlay-uri |
| `overlay_settings.py` | Widget setări overlay (Ticker/Ceas/Timer) |
| `presentation_editor.py` | Editor prezentări grafice (canvas QGraphics) |
| `dual_layout_editor.py` | Editor layout bilingv |
| `translation_dialog.py` | Dialog traducere automată cântări |
| `online_songs_tab.py` | Tab căutare cântări online |
| `splash_screen.py` | Ecranul de pornire |
| `migration.py` | Detectare și migrare baze de date vechi |
| `about_dialog.py` | Dialog „Despre Cantio" |
| `logger.py` | Configurare jurnal zilnic |
| `db_thread.py` | Execuție asincronă operații bază de date |
| `pixmap_cache.py` | Cache LRU pentru imagini (max 20, ~160 MB) |
| `lazy_imports.py` | Import leneș module grele (cv2, flask, fitz) |
| `text_utils.py` | Funcții wrap text și cuvinte sacre |
| `paths.py` | Detectare director de date per platformă |
| `interactive_tutorial.py` | Tutorial interactiv pentru utilizatori noi |

### 2.4 Fișierele Electron (directorul `display-electron/`)

```
display-electron/
├── main.js          ← Procesul principal Electron (server WebSocket)
├── display.html     ← Pagina HTML a ecranului de proiecție
├── display.js       ← Logica de randare (Canvas API)
├── package.json     ← Dependențe Node.js
└── node_modules/    ← Librării (ws, etc.)
```

### 2.5 Fișierul serviciu (.gps)

Fișierele de serviciu au extensia `.gps`. Intern sunt arhive ZIP care conțin:
- `service.json` — lista de itemi ai serviciului cu toate datele lor
- `metadata.json` — titlu serviciu, dată, autor, versiune aplicație

Asocierea extensiei `.gps` cu aplicația se înregistrează în Registrul Windows la prima rulare.

---

## 3. BAZA DE DATE — SCHEMA, INDECȘI, MIGRARE

### 3.1 Locație și configurare SQLite

Baza de date se află la `~/Cantio/profiles/<profil>/cantio.db`.
Se folosește modul WAL (Write-Ahead Logging) pentru a permite citiri concurente fără blocare:
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
PRAGMA foreign_keys = ON;
```

### 3.2 Tabelul `songs` — cântări

Coloanele tabelului principal de cântări:

| Coloană | Tip | Descriere |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Identificator unic autoincrementat |
| `title` | TEXT NOT NULL | Titlul cântării |
| `author` | TEXT | Autorul / compozitorul |
| `category` | TEXT | Categoria (ex. „Adorare", „Închinare") |
| `language` | TEXT | Codul limbii (ro, en, de, fr, hu, el, cu, es, pt) |
| `content` | TEXT | Textul complet al cântării (versuri) |
| `slides` | TEXT | JSON cu lista de slide-uri (text per strofă) |
| `notes` | TEXT | Note interne ale operatorului (nu se afișează pe proiector) |
| `formatting` | TEXT | JSON cu setările de formatare individuale |
| `translations` | TEXT | JSON cu traducerile în alte limbi |
| `title_normalized` | TEXT | Titlu fără diacritice (pentru căutare) |
| `author_normalized` | TEXT | Autor fără diacritice (pentru căutare) |
| `created_at` | TEXT | Data creării (ISO 8601) |

### 3.3 Tabelul FTS5 pentru căutare rapidă

```sql
CREATE VIRTUAL TABLE songs_fts USING fts5(
    title, author, content,
    content=songs,
    tokenize='unicode61 remove_diacritics 2'
);
```

Indexul FTS5 folosește tokenizatorul `unicode61` cu eliminare diacritice activată (`remove_diacritics 2`). Aceasta înseamnă că o căutare după „cantare" găsește și „cântare". Viteza tipică: sub 10 ms pe o bază cu 22.000 rânduri.

Căutarea se face cu `MATCH` pentru termeni FTS5. Dacă FTS5 eșuează, se face fallback automat la căutare `LIKE` standard pe coloana `title`.

### 3.4 Tabelele Biblie

Baza de date Biblie se află în același fișier `cantio.db` sau în `bible.db` separat.

**`bible_books`** — cărțile Bibliei:
- `id`, `name` (numele cărții), `abbrev` (abreviere), `testament` (OT/NT), `chapters` (număr capitole)

**`bible_verses`** — versetele:
- `id`, `book_id`, `chapter`, `verse`, `text`, `translation` (codul traducerii, ex. „VDC", „NKJV")

**`bible_translations`** — traducerile disponibile:
- `code` (ex. „VDC"), `name` (ex. „Versiunea Dumitru Cornilescu"), `language`

### 3.5 Setările implicite

Setările se stochează în tabelul `settings` cu perechi cheie-valoare. Valorile implicite pentru o instalare nouă:

| Cheie | Valoare implicită | Descriere |
|---|---|---|
| `font_family` | `Arial` | Fontul textului pe proiector |
| `font_size` | `48` | Dimensiunea fontului (pt) |
| `font_bold` | `true` | Text îngroșat |
| `font_italic` | `false` | Text înclinat |
| `text_color` | `#ffffff` | Culoarea textului |
| `outline_color` | `#000000` | Culoarea conturului textului |
| `outline_width` | `2` | Lățimea conturului (0–10 px) |
| `text_shadow` | `true` | Umbra textului activată |
| `bg_color` | `#000000` | Culoarea fundalului |
| `bg_type` | `color` | Tipul fundalului (color/gradient/image/video/camera/transparent) |
| `bg_image` | `` | Calea imaginii de fundal |
| `bg_opacity` | `0.5` | Opacitatea imaginii de fundal (0.0–1.0) |
| `margin` | `60` | Marginea textului față de margini (px la 1920×1080) |
| `line_spacing` | `1.4` | Spațierea între rânduri (1.0–3.0) |
| `text_align` | `center` | Alinierea orizontală (center/left/right) |
| `text_valign` | `center` | Alinierea verticală (center/top/bottom) |
| `transition` | `crossfade` | Tipul tranziției între slide-uri |
| `show_clock` | `false` | Afișare ceas pe proiector |
| `show_ticker` | `false` | Afișare ticker pe proiector |
| `screen_index` | `0` | Indexul ecranului de proiecție |
| `smart_paste_skip` | `false` | Sari peste dialogul Smart Paste |
| `lang` | `ro` | Limba interfeței |

### 3.6 Etichetele de slide (LABEL_COLORS)

Fiecare slide poate fi etichetat cu un tip de secțiune. Culorile etichetelor sunt definite astfel:

| Etichetă | Culoare hex |
|---|---|
| Strofa 1, Strofa 2, ... | `#6c7086` (gri) |
| Refren / Cor | `#89b4fa` (albastru) |
| Bridge | `#cba6f7` (violet) |
| Intro | `#a6e3a1` (verde) |
| Outro | `#f38ba8` (roșu) |
| Pod | `#fab387` (portocaliu) |
| Pre-Refren | `#f9e2af` (galben) |
| Tag | `#94e2d5` (turcoaz) |

### 3.7 Categoriile predefinite

```python
BUILTIN_CATEGORIES = [
    "Toate", "General", "Adorare", "Închinare",
    "Laudă", "Rugăciune", "Copii", "Crăciun",
    "Paști", "Botez", "Cununie", "Înmormântare",
    "Evanghelizare", "Misionar", "Colinde",
]
```

### 3.8 Migrarea bazelor de date vechi

La pornire, sistemul caută baze de date din versiuni anterioare:
- **v1** (monolitic): `~/Cantio/cantio.db`
- **v2** (separat): `~/Cantio/profiles/<profil>/songs.db`

Dacă se găsește una, apare un dialog de migrare care copiază fișierul (cu bară de progres 0–100%) în directorul profilului curent. Copierea se face în bucăți de 256 KB. Dacă migrarea eșuează, fișierul parțial este șters automat.

---

## 4. SISTEMUL DE PROFILURI ȘI SECURITATE

### 4.1 Directorul de profiluri

Profilurile se stochează în `~/Cantio/profiles/`. Fiecare profil are propriul director cu baza de date și fișierele de configurare complet independente.

### 4.2 Configurația unui profil

Fișierul `profile_config.json` conține:
- `password_hash` — hash SHA-256 al parolei (șirul gol înseamnă fără parolă)
- `restrictions` — dicționar cu restricții activate

### 4.3 Restricții per profil

Administratorul poate activa restricții individuale:

| Restricție | Efect |
|---|---|
| `no_delete_songs` | Dezactivează ștergerea cântărilor |
| `no_import` | Dezactivează importul de cântări |
| `no_settings` | Ascunde accesul la setările temei |
| `no_themes` | Ascunde tab-ul de teme |
| `no_new_profile` | Interzice crearea de profiluri noi |

### 4.4 Parola profilului

- Lungime minimă: 4 caractere
- Se stochează ca SHA-256 în `profile_config.json` (nu în clar)
- La schimbarea parolei, trebuie introdusă parola veche pentru confirmare
- Dacă un profil are parolă, la selectare apare un dialog de autentificare

### 4.5 Dialogul de selecție profil

La pornire, dacă există mai multe profiluri, apare `ProfileSelectDialog`. Acesta afișează:
- Lista tuturor profilurilor disponibile
- Buton „Nou" (dezactivat dacă restricția `no_new_profile` este activă)
- Buton „Deschide" → dacă profilul are parolă, apare `ProfilePasswordDialog`
- Buton „Setări profil" → permite configurarea parolei și restricțiilor

---

## 5. FEREASTRA PRINCIPALĂ DE CONTROL (OPERATOR)

### 5.1 Tema vizuală (APP_STYLE)

Fereastra principală folosește un stil dark complet, bazat pe paleta Catppuccin Mocha. Culorile principale:

| Element | Culoare hex |
|---|---|
| Fundal principal | `#11111b` |
| Fundal panouri | `#1e1e2e` |
| Fundal intrări text | `#1c1c1c` |
| Text principal | `#cdd6f4` |
| Text secundar | `#a6adc8` |
| Accent albastru | `#89b4fa` |
| Accent violet | `#cba6f7` |
| Accent verde | `#a6e3a1` |
| Accent roșu (erori) | `#f38ba8` |
| Borduri | `#313244` |
| Borduri hover | `#45475a` |

### 5.2 Structura panourilor ferestrei principale

Fereastra este împărțită în mai multe zone:

**Bara de sus (toolbar)**:
- Logo și titlul aplicației
- Butonul „GO LIVE" (sau „END LIVE")
- Buton ecran negru
- Indicator status proiector
- Buton setări

**Panoul stâng — Biblioteca de cântări**:
- Câmp de căutare cu debounce 250 ms
- Filtru categorie (dropdown)
- Lista virtuală paginată de cântări (PAGE_SIZE = 200)
- Butoane: Adaugă, Editează, Șterge, Import

**Panoul central — Slide-uri**:
- Titlul cântării curente
- Grila de miniaturi (sau lista de slide-uri)
- Selector mod vizualizare: XS / S / M / L / XL
- Editorul de versuri (text)
- Panoul de note al operatorului

**Panoul drept — Serviciu**:
- Lista itemilor din serviciu
- Butoane: Adaugă la serviciu, Mută sus/jos, Șterge
- Buton Salvează serviciu / Deschide serviciu

**Panoul de preview**:
- Imagine 320×180 px actualizată la 15 fps
- Afișează exact ce apare pe proiector

### 5.3 Dimensiunile miniaturilor de slide

Fereastra de operator permite 5 mărimi de miniaturi pentru slideuri:

| Cod | Lățime | Înălțime | Utilizare |
|---|---|---|---|
| XS | 120 px | 68 px | Vedere compactă, multe slide-uri |
| S | 168 px | 94 px | Mărimea implicită |
| M | 220 px | 124 px | Medie |
| L | 300 px | 169 px | Mare |
| XL | 400 px | 225 px | Foarte mare, text vizibil clar |

### 5.4 Modelul virtual de cântări (SongsModel)

Lista de cântări folosește un model virtual cu paginare:
- `PAGE_SIZE = 200` — se încarcă câte 200 de cântări pe pagină
- Debounce la căutare: **250 ms** — așteptați 250 ms după ultima tastă înainte de a interoga baza de date
- Afișarea fiecărei cântări în listă: 2 rânduri — titlu (font Segoe UI 10pt) + autor (font Segoe UI 8pt)
- Înălțimea unui rând: 40 px dacă are autor, 28 px fără autor

### 5.5 Scurtăturile de tastatură

13 scurtături definite în aplicație:

| Scurtătură | Acțiune |
|---|---|
| Ctrl+F | Focalizare câmp căutare cântări |
| ← / → | Slide anterior / următor |
| ↑ / ↓ | Cântare anterioară / următoare în serviciu |
| Ctrl+B | Ecran negru (Black screen) |
| Ctrl+L | GO LIVE / oprire live |
| Ctrl+S | Salvare serviciu |
| Ctrl+O | Deschidere serviciu |
| Ctrl+N | Cântare nouă |
| Ctrl+E | Editare cântare curentă |
| F4 | Setări temă |
| F11 | Deschide / închide ecranul de proiecție |
| Ctrl+Z | Anulare ultimă acțiune |
| Escape | Ecran negru sau ieșire mod live |

---

## 6. BIBLIOTECA DE CÂNTĂRI — CĂUTARE, AFIȘARE, EDITARE

### 6.1 Câmpul de căutare

Câmpul de căutare folosește debounce de **250 ms**. Căutarea se face simultan în:
- Titlul cântării (coloana `title`)
- Titlul normalizat fără diacritice (coloana `title_normalized`)
- Autorul (coloana `author`)

Algoritmul de căutare:
1. Se încearcă mai întâi cu FTS5 MATCH (sub 10 ms)
2. Dacă FTS5 eșuează sau nu returnează rezultate, se folosește LIKE `%query%`

### 6.2 Filtrele de căutare

Deasupra listei există un dropdown cu categorii. Selectarea „Toate" elimină filtrul de categorie. Celelalte opțiuni filtrează după coloana `category` a cântării.

### 6.3 Editorul de cântare (SongEditorDialog)

Dimensiunea minimă: 700×580 px. Câmpurile editorului:

| Câmp | Tip | Observații |
|---|---|---|
| Titlu * | TextEdit | Obligatoriu |
| Autor | TextEdit | Opțional |
| Categorie | ComboBox editabil | Include categoriile predefinite |
| Limbă | ComboBox | ro, el, cu, en, fr, de, hu, es, pt |
| Note operator | TextArea (60px înălțime fixă) | Fund `#1a1a0a`, text `#ccaa44`, nu apare pe proiector |
| Versuri | TextArea expandabilă | Font Consolas 11pt, slide-urile separate prin linie goală |

### 6.4 Structura versurilor

Versurile sunt stocate ca text simplu, cu slide-urile separate prin **linii goale** (linie goală = separator de slide). Exemplu:

```
Primul rând al primului slide
Al doilea rând al primului slide

Primul rând al celui de-al doilea slide
Al doilea rând al celui de-al doilea slide
```

La salvare, textul se parsează automat și se generează lista `slides` (JSON array cu câte un string per slide).

### 6.5 Smart Paste — formatare automată la lipire

Când utilizatorul lipește text în editorul de versuri, dacă textul:
- Nu are linii goale ȘI are mai mult de 3 linii, SAU
- Conține markeri de strofă/refren

...apare dialogul **Smart Paste** (dacă nu este dezactivat din preferințe).

Dialogul Smart Paste (680×520 px) oferă:
- Previzualizare comparativă: Original (stânga) | Reformatat (dreapta)
- Opțiuni:
  - „Elimină nr. strofă (1. 2.)" — șterge numerotarea strofelor
  - „Elimină markeri refren (R: Ref:)" — șterge prefixele de refren
  - „Împarte linii lungi (>80 car.)" — activat implicit, împarte la virgulă/punct-virgulă
- Checkbox „Nu mai întreba (folosește reformatat automat)" — salvat în setări ca `smart_paste_skip`

Markerii detectați de Smart Paste: `1.`, `2)`, `Strofa 1`, `R:`, `R.`, `Ref:`, `Refren:`, `REFREN`, `Chorus:`, `/:`, `Pod:`, `Bridge:`, `Pre-refren:`

### 6.6 Normalizarea diacriticelor

Câmpurile `title_normalized` și `author_normalized` conțin versiunile fără diacritice ale titlului și autorului. Aceasta permite căutarea „cantare" să găsească „cântare" și invers. Normalizarea se aplică automat la salvare.

### 6.7 Dialogul Uppercase

Permite conversia versurilor la majuscule:
- Pentru toate cântările din bibliotecă
- Pentru cântările dintr-o categorie selectată
- Pentru cântarea selectată curent

Acțiunea este ireversibilă (afișează avertisment explicit).

### 6.8 Dialogul Split Lines

Permite împărțirea slide-urilor la un număr fix de rânduri (1–20 rânduri per slide). Afișează previzualizare a rezultatului. Acțiunea modifică permanent structura slide-urilor.

---

## 7. LISTA DE SERVICIU (PLAYLIST)

### 7.1 Structura unui serviciu

Un serviciu conține o listă ordonată de itemi. Fiecare item poate fi:
- O cântare din bibliotecă (cu referință la ID)
- Un verset biblic
- O prezentare grafică
- Un element media (imagine, video)
- Un slide text personalizat

### 7.2 Operații disponibile

- **Adaugă**: adaugă cântarea selectată la sfârșitul listei
- **Mută sus/jos**: reordonează itemii
- **Duplică**: copiază un item
- **Șterge**: elimină itemul din serviciu
- **Drag-and-drop**: reordonare prin tragere

### 7.3 Salvarea serviciului

Serviciile se salvează ca fișiere `.gps` (arhivă ZIP):
- `service.json` — toate datele itemilor
- `metadata.json` — titlu, dată, autor, versiune Cantio

Ultimele 5 servicii deschise se memorează în `~/Cantio/recent_services.json`.

### 7.4 Asocierea fișierelor .gps pe Windows

La prima rulare pe Windows, aplicația înregistrează în Registrul Windows asocierea extensiei `.gps` cu Cantio. Double-click pe un fișier `.gps` deschide direct Cantio cu serviciul respectiv.

---

## 8. EDITORUL DE SLIDE-URI ȘI MINIATURI

### 8.1 Componenta SlideThumbnail

Fiecare miniatură de slide este un widget independent care:
- Se randează într-un pixmap off-screen la prima afișare (cache)
- Refolosește cache-ul la afișările ulterioare (nu redesenează dacă nimic nu s-a schimbat)
- Se invalidează prin `mark_dirty()` la orice schimbare de text sau setări
- Are indicator de focus: bordura albastră `#5294e2` (2 px) când este selectat
- Are bordura gri `#3a3a3a` (1 px) la hover, `#222222` normal

Fiecare miniatură afișează:
- Fundalul (culoare sau gradient)
- Textul slide-ului scalat (font_size × scale, unde scale = lățime_miniatură / 1920)
- Eticheta secțiunii (badge colorat 14px înălțime, în colțul stânga-sus al slide-ului)
- Bara de jos (22 px înălțime) cu:
  - Numărul slide-ului (badge 22×14 px, rotunjit 3 px)
  - Primele 28 caractere ale textului (trunchiare cu „…")

### 8.2 Meniul contextual al miniaturii

Click-dreapta pe o miniatură deschide meniu cu:
- Mută sus
- Mută jos
- La început (move_first)
- La sfârșit (move_last)
- Duplică
- Schimbă eticheta → deschide dialog cu lista de etichete predefinite
- Șterge slide (afișat cu roșu `#f44336`)

### 8.3 Etichetele predefinite de slide

Dialog de selectare etichetă cu lista:
`Strofa 1, Strofa 2, Strofa 3, Strofa 4, Strofa 5, Strofa 6, Refren, Cor, Bridge, Pre-Refren, Intro, Outro, Pod, Final`

### 8.4 Auto-detectare etichetă

Dacă primul rând al slide-ului conține cuvinte cheie, eticheta este detectată automat:
- `refren`, `chorus` → „Refren"
- `bridge` → „Bridge"
- `intro` → „Intro"
- `outro` → „Outro"
- `verse`, `strofă`, `strofa` → „Strofa"
- `hallelujah`, `alleluja` → „Hallelujah"
- `coda` → „Coda"
- `tag` → „Tag"
- `pre` → „Pre-Chorus"

### 8.5 Modul de afișare a listei de slide-uri

Pe lângă vizualizarea cu miniaturi, există și un mod de listă text (SlideListDelegate). În acest mod:
- Fiecare rând are înălțimea adaptată numărului de linii: `max(44, linii × 20 + 12×2)` px
- Coloane: număr badge (32 px lățime) + text complet al slide-ului (Consolas 11pt)
- Fundal selectat: `#1c3a5a`, hover: `#1e1e1e`, normal: `#141414`

---

## 9. MOTORUL DE AFIȘARE ELECTRON (FEREASTRA LIVE)

### 9.1 Procesul Electron

Cantio pornește Electron ca un subprocess. Calea executabilului se alege în ordine de prioritate:
1. `CantioDisplay.exe` (versiune compilată, distribuție oficială)
2. `node_modules/electron/dist/electron.exe` (instalare locală npm)
3. `npx electron` sau `electron.cmd` (instalare globală)

### 9.2 Serverul WebSocket (portul 7432)

Procesul Electron pornește un server WebSocket pe `ws://localhost:7432`. Toate comenzile de la Python vin prin acest canal.

La conectare, Electron trimite imediat:
```json
{"type": "ready", "screens": [...]}
```

unde `screens` este lista ecranelor disponibile cu proprietățile lor.

### 9.3 Proprietățile unui ecran (din `get_screens`)

Fiecare ecran din lista `screens` are:
- `index` — indexul în lista tuturor ecranelor
- `id` — ID-ul unic al ecranului (din API-ul Electron)
- `label` — eticheta ecranului (ex. „\\.\DISPLAY2")
- `name` — „Primary" sau „Screen 1", „Screen 2"
- `bounds` — obiect `{x, y, width, height}`
- `width`, `height` — rezoluția ecranului
- `x`, `y` — poziția (față de ecranul primar)
- `primary` — `true` dacă este ecranul primar
- `scaleFactor` — factorul de scalare DPI
- `screen_index` — index compatibil cu `openDisplay()`: 0 = primul ecran secundar, 1 = al doilea secundar, etc.

### 9.4 Logica de selecție a ecranului la deschidere

Funcția `openDisplay(screenIdx, windowId, windowName, isTransparent)`:
- Dacă `screenIdx = 0` și există ecrane secundare → se folosește primul ecran secundar
- Dacă `screenIdx > 0` și există atâtea ecrane secundare → se folosește `secondaryDisplays[screenIdx - 1]`
- Altfel (fallback) → se folosește `displays[min(screenIdx, displays.length - 1)]`

### 9.5 Fereastra de proiecție — creare și animații

La deschidere, fereastra Electron:
1. Creează `BrowserWindow` cu:
   - Poziție și dimensiune = bounds-ul ecranului țintă
   - `frame: false` (fără bordură)
   - `alwaysOnTop: true`
   - `skipTaskbar: true`
   - `transparent: true/false` (după setare)
   - `backgroundColor: '#00000000'` (transparent) sau `'#000000'`
2. Încarcă `display.html`
3. La `did-finish-load`:
   - Setează bounds explicit
   - Afișează fereastra (`.show()`)
   - După 200 ms: activează fullscreen
   - Pornește **fade-in** easeOutCubic: 500 ms, ~60 fps (16 ms interval)

Formula fade-in: `eased = 1 - Math.pow(1 - progress, 3)` (easeOutCubic)

### 9.6 Închiderea ferestrei de proiecție

La `closeDisplay()`, fereastra se stinge treptat (fade-out):
- Scade opacitatea cu **0.08** la fiecare **16 ms**
- Când opacitatea ajunge la 0, fereastra se închide

### 9.7 Comenzile WebSocket acceptate

Toate comenzile sunt obiecte JSON cu câmpul `type` (sau `cmd` pentru compatibilitate veche) și `window_id`:

| Comandă | Efect |
|---|---|
| `ping` | Răspunde cu `{"type": "pong", "resp": "pong"}` |
| `get_screens` | Returnează lista de ecrane |
| `open` | Deschide fereastră pe ecranul specificat |
| `close` | Închide fereastra (cu fade-out) |
| `quit` | Închide întregul proces Electron (după 200 ms) |
| `show_text` | Afișează text pe proiector |
| `black` | Ecran negru |
| `settings` | Actualizează setările de afișare |
| `ticker` | Pornește ticker-ul cu text |
| `hide_ticker` | Ascunde ticker-ul |
| `timer` | Pornește countdown-ul |
| `stop_timer` | Oprește countdown-ul |
| `clock` | Afișează/ascunde ceasul |
| `projector_off` | Oprire proiector (ecran negru complet) |
| `logo` | Afișează logo-ul |
| `slide_image` | Afișează o imagine de slide |
| `show_slide_image` | Idem |
| `transparent` | Comutare modul transparent |
| `clear_text` | Șterge textul de pe ecran |
| `freeze` | Blochează actualizările afișajului |
| `unfreeze` | Deblochează actualizările |
| `ticker_advanced` | Ticker cu setări avansate |
| `hide_ticker_effect` | Ascunde ticker cu efect |
| `set_transparent` | Recreează fereastra cu transparent=true/false |

### 9.8 Broadcast-ul comenzilor

`broadcast(windowId, msg)` trimite comanda:
1. Prin IPC: `win.webContents.send('render', msg)` — calea rapidă
2. Fallback: `executeJavaScript("window._handleRender(...)")` — pentru cazurile în care IPC nu funcționează

Dacă `windowId` este `null` sau `undefined`, comanda se trimite la TOATE ferestrele deschise.

---

## 10. RANDAREA TEXTULUI PE ECRANUL DE PROIECȚIE

### 10.1 Cele două canvase (display.html)

Pagina HTML a ecranului de proiecție conține două elemente `<canvas>` suprapuse:
- `#canvas-prev` — z-index: 1 — canvas-ul „vechi" (slide anterior)
- `#canvas-curr` — z-index: 2 — canvas-ul „curent" (slide nou)

Plus două elemente pentru fundal (z-index: 0):
- `<video id="bg-video">` — pentru fundal video/cameră
- `<img id="bg-image">` — pentru fundal imagine

### 10.2 Tranzițiile între slide-uri

La schimbarea unui slide, se produce tranziție vizuală. Duratele definite:

| Tranziție | Durată |
|---|---|
| `fade` | 500 ms |
| `crossfade` | 350 ms |
| `slide_left` | 350 ms |
| `zoom_in` | 400 ms |

### 10.3 Procesarea textului (processText)

Înainte de afișare, textul trece prin `processText()`:
1. Dacă `uppercase = true` → tot textul devine majuscule cu `.toUpperCase()`
2. Dacă sunt definite cuvinte sacre (`sacred_words` în setări) și `sacred_caps = true`:
   - Cuvintele sacre sunt identificate case-insensitive
   - Înlocuite cu forma lor canonică (sau cu majuscule dacă `sacred_allcaps = true`)

**Cuvintele sacre implicite**: Jesus, Isus, Iisus, God, Dumnezeu, Hristos, Christ, Domnul, Holy Spirit, Duhul Sfânt, Emanuel, Tatăl, Fiul, Mesia, Aleluia, Amin

### 10.4 Dimensionarea automată a textului (drawText)

Algoritmul `drawText()` în `display.js` reduce dimensiunea fontului cu **2 px** la fiecare iterație până textul se încadrează în zona disponibilă. Dimensiunea minimă este **10 px**.

Zona disponibilă = lățimea și înălțimea ecranului minus marginile (`margin` din setări, implicit 60 px la 1920 px).

Dacă ticker-ul este activ, înălțimea disponibilă se reduce cu înălțimea ticker-ului (implicit 40 px).

### 10.5 Modurile de text box (text_box_mode)

Trei moduri de poziționare a textului:

| Mod | Comportament |
|---|---|
| `per_line` | Fiecare rând se poziționează independent |
| `full_block` | Toate rândurile formează un bloc compact centrat |
| `full_width` | Textul se extinde pe toată lățimea disponibilă |

### 10.6 Alinierea textului

Alinierea orizontală (`text_align`): `center`, `left`, `right`
Alinierea verticală (`text_valign`): `center`, `top`, `bottom`

### 10.7 Conturul textului (outline)

Conturul se desenează în 8 direcții (N, NE, E, SE, S, SW, W, NW) la distanța `outline_width` px. Culoarea conturului: `outline_color` (implicit `#000000`). Grosimea conturului: 0–10 px.

### 10.8 Randarea Python (renderer.py)

Funcția `render_frame(painter, state, width, height, scale)` din `renderer.py` desenează un frame complet în această ordine:

1. Fundal culoare solidă (`bg_color`)
2. Frame video (dacă există)
3. Imagine fundal (scalată și centrată cu `KeepAspectRatioByExpanding`)
4. Dacă `logo_active`: afișează logo centrat + overlay-uri, oprire
5. Dacă `projector_off`: ecran complet negru, oprire
6. Versurile textului curent (cu opacitatea curentă pentru tranziție)
7. Overlay-uri: ticker, ceas, countdown

### 10.9 Randarea în preview (render_engine.py)

Previzualizarea rulează pe un fir de execuție separat (QThread, prioritate `HighPriority`):
- Rezoluție frame complet: **1920×1080 px** la **60 fps** (interval 16 ms)
- Rezoluție preview: **320×180 px** la **15 fps** (interval 67 ms)
- Se randează ca `QImage` (thread-safe) → se convertește la `QPixmap` pe firul principal

---

## 11. FUNDAL — TIPURI, TRANZIȚII, VIDEO, CAMERĂ

### 11.1 Tipurile de fundal

Câmpul `bg_type` din setări determină tipul de fundal:

| Valoare | Descriere |
|---|---|
| `color` | Culoare solidă (`bg_color`) |
| `gradient` | Gradient liniar sau radial |
| `image` | Imagine statică |
| `video` | Fișier video în buclă |
| `camera` | Feed live de la cameră |
| `animated_gradient` | Gradient animat (mișcare lentă) |
| `transparent` | Fundal complet transparent (necesită fereastră transparentă) |

### 11.2 Tipurile de gradient

Câmpul `bg_grad_dir` (direcția gradientului):

| Valoare | Efect |
|---|---|
| `Sus→Jos` | Gradient vertical de sus în jos |
| `Stânga→Dreapta` | Gradient orizontal de la stânga la dreapta |
| `Diagonală` | Gradient diagonal (stânga-sus → dreapta-jos) |
| `Radial` | Gradient radial (circular, din centru spre exterior) |

Culorile gradientului: `bg_grad_c1` (culoarea de start) și `bg_grad_c2` (culoarea de final).

### 11.3 Imaginea de fundal

- Câmpul `bg_image`: calea absolută a imaginii
- Câmpul `bg_opacity`: opacitatea imaginii (0.0 = invizibil, 1.0 = opac complet)
- Scalare: `KeepAspectRatioByExpanding` + crop centrat (ca `object-fit: cover` în CSS)

### 11.4 Video de fundal

Decodarea video se face cu OpenCV (`VideoDecodeThread` din `media_engine.py`):
- Frame-urile sunt emise ca array-uri numpy RGB
- Rata maximă: TARGET_FPS = 30 fps
- Mecanismul back-pressure: flag `_frame_pending` — nu se emite un frame nou până ce cel anterior nu a fost procesat
- Rezoluție target: 1920×1080 px (redimensionat cu `INTER_LINEAR`)
- La final, videoul se reia automat (buclă)

### 11.15 Camera live

- `CameraThread` (din `media_tab.py`) captează de la camera cu indexul specificat
- Setare buffer: `CAP_PROP_BUFFERSIZE = 1` (minimizare latență)
- Conversia culorilor: BGR (format OpenCV) → RGB
- Redimensionare la 1920×1080 cu `INTER_LINEAR`
- Detectarea automată a camerelor disponibile: testează indexele 0–7

---

## 12. OVERLAY-URI — TICKER, CEAS, TIMER

### 12.1 Ticker-ul

Ticker-ul este o bandă text care derulează orizontal în partea de jos a ecranului.

**Setările implicite ale ticker-ului**:

| Setare | Valoare implicită |
|---|---|
| `font_family` | `Segoe UI` |
| `font_size` | 14 pt |
| `bold` | false |
| `italic` | false |
| `color` | `#ffffff` |
| `bg_color` | `#000000cc` (negru cu 80% opacitate) |
| `bg_opacity` | 85% |
| `height` | 40 px |
| `position` | `bottom` |
| `speed` | 3 |
| `prefix` | `` (gol) |
| `separator` | `  ◆  ` |
| `animation` | `scroll_left` |
| `border_color` | `#333333` |
| `border_width` | 0 px |

**Animația de intrare**: `slide_up` (durată 400 ms implicit) — ticker-ul urcă de jos în poziție.
**Animația de ieșire**: `slide_down` — ticker-ul coboară și dispare.

**Viteza de derulare**: Viteza în px/secundă = `speed × 60`. Deci la speed=3: 180 px/sec. Timer de animație: 16 ms (60 fps). Mișcarea per frame: `speed` px.

**Actualizarea stării ticker**: LiveState.py actualizează ticker-ul la **16 ms** (60 fps).

### 12.2 Ceasul

Ceasul poate fi afișat în colțul ecranului de proiecție.

**Setările implicite ale ceasului**:

| Setare | Valoare implicită |
|---|---|
| `font_family` | `Segoe UI` |
| `font_size` | 16 pt |
| `bold` | true |
| `color` | `#ffffff` |
| `format` | `HH:MM:SS` |
| `show_date` | false |
| `position` | `top_right` |
| `bg` | `transparent` |
| `padding` | 8 px |
| `border_radius` | 4 px |
| `shadow` | true |
| `size_pct` | 8 (% din înălțimea ecranului) |

**Pozițiile posibile ale ceasului**:
`top_right` (implicit), `top_left`, `top_center`, `bottom_right`, `bottom_left`, `bottom_center`

**Actualizarea ceasului**: LiveState actualizează ceasul la **500 ms**.

### 12.3 Timer-ul (countdown)

Timer-ul afișează numărătoarea inversă pe ecranul de proiecție.

**Setările implicite ale timer-ului**:

| Setare | Valoare implicită |
|---|---|
| `font_family` | `Segoe UI` |
| `font_size` | 32 pt |
| `bold` | true |
| `color` | `#ffffff` |
| `warning_color` | `#ff8800` (portocaliu la aproape de final) |
| `finished_color` | `#f44336` (roșu la 0) |
| `flash_at_zero` | true |
| `sound_at_zero` | `none` |
| `format` | `MM:SS` |
| `position` | `center_top` |
| `count_up` | false |

În `display.js`, timer-ul rulat se afișează cu:
- Culoarea verde: `#00ff88`
- Font monospaced
- Poziție: stânga-sus (top-left)

**Actualizarea countdown-ului**: LiveState actualizează la **1000 ms** (o dată pe secundă).

### 12.4 LiveState — starea centralizată

`LiveState` este un singleton care menține starea curentă a proiectorului. Are observatori (pattern Observer):
- `add_observer(callback)` / `remove_observer(callback)` / `notify()`
- Timere interne:
  - Ticker: 16 ms (60 fps)
  - Ceas: 500 ms
  - Countdown: 1000 ms

### 12.5 Freeze (înghețarea afișajului)

Comanda `freeze` blochează TOATE actualizările randării în display.js. Nicio comandă de tip `show_text`, `black`, `settings` etc. nu produce efect vizual cât timp freeze-ul este activ. `unfreeze` deblochează.

---

## 13. MODULUL BIBLIE

### 13.1 Structura panoului Biblie

Panoul Biblie (`BibleControlTab`) permite navigarea și afișarea versetelor biblice. Are:

**Rândul de traduceri duale**:
- Dropdown „Traducere 1" + Dropdown „Traducere 2"
- Checkbox „Dual" — activează modul dual (ambele traduceri afișate simultan)

**Antetul**:
- Titlu „📖 Biblie"
- Indicator „Carte Chapter" (ex. „Ioan 3")
- Butoane Prev (capitol anterior) / Next (capitol următor)

**Lista versetelor**:
- Fiecare verset: `{nr}.  {text}`
- Click pe verset → trimite versul live pe proiector
- Selectat = fundal `#313244`, text `#cba6f7`

**Zona „Verset curent"** (GroupBox):
- Text complet al versetului curent (font 13 px)
- Referința (ex. „Ioan 3:16") în albastru `#89b4fa`
- Buton „Trimite live" → background `#1c3a5a`, hover `#2a5a8a`

**Hint tastatură** (jos): text gri `#45475a`, font 10 px, centrat

### 13.2 Navigarea cu tastatura

- `←`/`↑` → verset anterior
- `→`/`↓` → verset următor
- `Enter` → trimite versul curent live

### 13.3 Modul dual-traducere

În modul dual, la trimiterea live, textul afișat conține ambele traduceri. Traducerile sunt afișate:
- Prima traducere: sus / stânga (zona „original" din layout)
- A doua traducere: jos / dreapta (zona „translation" din layout)

---

## 14. TEME VIZUALE — EDITOR, CARDURI, PREVIZUALIZARE

### 14.1 Tab-ul Teme

Tab-ul Teme (`ThemesTab`) este împărțit în două coloane printr-un separator:

**Stânga — Grid de teme**:
- Selector tip: „🎵 Songs" / „📖 Bible" (teme separate pentru cântări și Biblie)
- Grila de carduri cu previzualizare PNG
- Butoane: Adaugă (＋), Duplică (⧉), Șterge (🗑), Salvează (💾)

**Dreapta — Detalii temă selectate**:
- Titlul temei (font 14px bold)
- Buton „Editează temă" (fundal `#313244`)
- Buton „Setează ca implicit" (fundal `#a6e3a1`, text `#1e1e2e`)
- Buton „Duplică" + Buton „Șterge" (roșu `#f38ba8`, bordură `#f38ba8`)

### 14.2 Generarea previzualizării temei

Funcția `generate_theme_preview()` din `theme_editor.py` creează `QImage` (nu `QPixmap`, pentru că se apelează din fire de execuție secundare unde `QPixmap` nu este permis).

Dimensiunile previzualizării în funcție de raportul de aspect:
- **16:9** → 320×180 px
- **4:3** → 320×240 px
- **21:9** → 320×137 px

### 14.3 Editorul vizual de temă (ThemeVisualEditor)

Editorul de temă conține `CollapsibleSection` — secțiuni colapsabile. Stilul general folosește paleta Catppuccin: fundal `#1e1e2e`, accent `#cba6f7`.

### 14.4 Teme pentru Songs vs. Bible

Aplicația menține seturi de teme separate:
- Temele de tip **Songs** se aplică la afișarea cântărilor
- Temele de tip **Bible** se aplică la afișarea versetelor biblice

Comutarea între tipuri se face cu butoanele selector din stânga tab-ului.

---

## 15. SETĂRI — FEREASTRĂ, CÂMPURI, VALORI IMPLICITE

### 15.1 Structura ferestrei de setări

`WindowPerSettingsDialog` (sau `SettingsDialog`) este împărțit în tab-uri:

1. **Font** — familia, dimensiunea, stilul
2. **Culori** — text, contur, fundal
3. **Fundal** — imagine + opacitate
4. **Layout** — marjă, spațiere linii, tranziție, aliniere
5. **Overlay-uri** — ceas, ticker, timer

### 15.2 Tab-ul Font

Câmpuri disponibile:

| Câmp | Tip | Interval valori | Implicit |
|---|---|---|---|
| Familie font | QFontComboBox | Fonturile instalate | Arial |
| Dimensiune | QSpinBox | 12–200 pt | 48 pt |
| Bold | QCheckBox | true/false | true |
| Italic | QCheckBox | true/false | false |

### 15.3 Tab-ul Culori

| Câmp | Tip | Implicit |
|---|---|---|
| Culoare text | ColorButton 48×28 px | `#ffffff` |
| Culoare contur | ColorButton 48×28 px | `#000000` |
| Grosime contur | QSpinBox 0–10 | 2 |
| Culoare fundal | ColorButton 48×28 px | `#000000` |

### 15.4 Tab-ul Fundal

| Câmp | Tip | Descriere |
|---|---|---|
| Imagine fundal | QLineEdit + buton Browse | Calea absolută a imaginii |
| Opacitate imagine | QSlider 0–100 | 0 = transparent, 100 = opac; implicit 50 |

### 15.5 Tab-ul Layout

| Câmp | Interval | Implicit |
|---|---|---|
| Margine | 0–400 px | 60 px |
| Spațiere rânduri | 1.0–3.0 | 1.4 |
| Tranziție | fade / crossfade / slide_left / zoom_in | crossfade |
| Aliniere orizontală | center / left / right | center |
| Aliniere verticală | center / top / bottom | center |

### 15.6 Tab-ul Overlay-uri

Conține widget-ul `OverlaySettingsWidget` cu 3 sub-tab-uri:
- **📢 Ticker** — toate setările ticker-ului (descrise la secțiunea 12)
- **🕐 Ceas** — toate setările ceasului
- **⏱ Timer** — toate setările timer-ului

Buton „👁 Previzualizează overlays" — afișează previzualizare live.

---

## 16. SERVER WEB PENTRU CONTROL DE LA DISTANȚĂ (MOBIL)

### 16.1 Prezentare generală

`remote_server.py` pornește un server Flask + SocketIO pe **portul 5050**. Permite controlul aplicației de pe un telefon sau tabletă conectat la aceeași rețea Wi-Fi.

### 16.2 Detectarea adresei IP locale

Adresa IP locală se detectează automat:
1. Se deschide un socket UDP și se „conectează" (fără a trimite date) la `8.8.8.8:80`
2. Se citește adresa locală din socket

Dacă acest mecanism eșuează, se folosește `socket.gethostbyname(socket.gethostname())`.

### 16.3 Codul QR

La pornirea serverului se generează automat un cod QR (cu biblioteca `qrcode`) care conține URL-ul complet al interfeței web mobile (ex. `http://192.168.1.100:5050`). QR-ul se poate afișa în fereastra de operator.

### 16.4 Endpoint-urile API

| Endpoint | Metodă | Răspuns |
|---|---|---|
| `/` | GET | Pagina web principală (HTML cu interfața mobilă) |
| `/api/state` | GET | Starea curentă a proiectorului (JSON) |
| `/api/songs` | GET | Lista tuturor cântărilor |
| `/api/songs/search/<query>` | GET | Căutare cântări |
| `/api/song/<id>` | GET | Detaliile unei cântări (cu slide-uri) |

### 16.5 Structura stării returnate de `/api/state`

Dicționarul `_state` intern conține:
- `current_text` — textul afișat curent pe proiector
- `current_title` — titlul cântării curente
- `slide_index` — indexul slide-ului curent
- `slide_count` — numărul total de slide-uri al cântării curente
- `is_live` — dacă proiectorul este activ (true/false)
- `is_frozen` — dacă afișajul este înghețat
- `ticker` — textul ticker-ului activ (sau null)
- `countdown_remaining` — secundele rămase la countdown
- `service_items` — lista completă a serviciului curent
- `service_index` — indexul itemului activ din serviciu
- `song_list` — lista de cântări disponibile
- `slides` — slide-urile cântării curente
- `display_open` — dacă fereastra de proiecție este deschisă
- `current_song` — datele complete ale cântării curente

---

## 17. MONITORUL DE SCENĂ (STAGE MONITOR)

### 17.1 Ce este Stage Monitor

Monitorul de scenă este o fereastră separată destinată interpreților de pe scenă (vocaliști, instrumentiști). Afișează informații care nu apar pe ecranul de proiecție principal, cum ar fi versul următor, notițe, timer.

### 17.2 Tipurile de widget-uri disponibile

| Tip widget | Descriere |
|---|---|
| `CURRENT_SLIDE` | Textul slide-ului curent (ce vede publicul) |
| `NEXT_SLIDE` | Textul slide-ului următor (preview pentru interpretul) |
| `CLOCK` | Ceasul curent |
| `TIMER` | Countdown-ul curent |
| `NOTES` | Notele operatorului (câmpul `notes` al cântării) |
| `CUSTOM_TEXT` | Text personalizat configurat manual |
| `IMAGE` | O imagine configurată de operator |

### 17.3 Configurarea layout-ului

Layout-ul monitor de scenă se salvează în `stage.json` din directorul profilului curent. Fiecare widget are poziție și dimensiune configurabile.

---

## 18. IMPORT ȘI EXPORT — FORMATE SUPORTATE

### 18.1 Formatele de import

Cantio poate importa cântări din diverse formate:

| Format | Descriere | Mod de detectare |
|---|---|---|
| TXT | Fișier text simplu | Extensia `.txt` |
| DOCX | Document Microsoft Word | Extensia `.docx` (via python-docx) |
| PDF | Document PDF | Extensia `.pdf` (via PyMuPDF/fitz) |
| VideoPsalm JSON | Export din VideoPsalm | Structură JSON specifică |
| EasyWorship 7 (RTF) | Export EW7 RTF | Detectat prin structura fișierului |
| EasyWorship 7 (two-file) | Export EW7 (două fișiere) | Detectat prin perechea de fișiere |

### 18.2 Extragerea textului din PDF

Se folosește PyMuPDF (fitz) care se importă leneș (lazy import) la primul apel. Extragerea textului respectă structura paginilor.

### 18.3 Extragerea textului din DOCX

Se folosește python-docx, de asemenea importat leneș. Se extrag toate paragrafele documentului.

### 18.4 Curățarea textului RTF

Funcția `strip_rtf()` din `importer.py` elimină tag-urile RTF și returnează textul simplu.

### 18.5 Conversia text → slide-uri

Funcția `text_to_slides()` din `importer.py` împarte un text în slide-uri folosind linia goală ca separator (același mecanism ca la editarea directă).

### 18.6 Firul de execuție al importului

`ImportWorker` este un `QThread` care emite semnalul `progress(int)` cu valori 0–100 pe parcursul importului. Interfața nu se blochează în timpul importului.

### 18.7 Istoricul importurilor

Ultimele 50 de importuri se salvează în `~/Cantio/import_history.json` (data, calea fișierului, numărul de cântări importate).

### 18.8 Exportul bazei de date

`export_db_json()` exportă toată baza de date ca JSON. `import_db_json()` importă dintr-un JSON exportat anterior.

---

## 19. TRADUCEREA AUTOMATĂ A CÂNTĂRILOR

### 19.1 Serviciul de traducere

Traducerea automată se face prin biblioteca `deep-translator` (GoogleTranslator), care folosește Google Translate fără cheie API.

Importul se face leneș: `from lazy_imports import get_translator`.

### 19.2 Limbile disponibile pentru traducere

16 limbi disponibile în dialogul de traducere:
ro (Română), en (English), de (Deutsch), fr (Français), hu (Magyar), es (Español), it (Italiano), pt (Português), ru (Русский), uk (Українська), pl (Polski), cs (Čeština), sk (Slovenčina), bg (Български), sr (Српски), hr (Hrvatski)

### 19.3 Algoritmul de traducere inteligentă

Funcția `translate_text_smart()` traduce text-ul linie cu linie, păstrând exact structura:
- Liniile goale (separatorii de slide) sunt păstrate neschimbate
- Fiecare linie nevărsată (non-empty) este tradusă individual
- Dacă traducerea returnează string gol, linia originală este păstrată

Avantaj: structura slide-urilor rămâne identică cu originalul după traducere.

### 19.4 Firul de execuție al traducerii

`_TranslateThread` este un `QThread` care emite:
- `progress(done, total)` — progresul (linii traduse / linii totale)
- `finished(text)` — textul tradus complet
- `error(message)` — dacă Google Translate returnează eroare

### 19.5 Stocarea traducerilor

Traducerile sunt stocate în coloana `translations` a tabelului `songs` ca JSON:
```json
{
    "en": "English translation text...",
    "de": "Deutscher Übersetzungstext..."
}
```

### 19.6 Layoutul dual-limbaj

Editorul de layout dual (`DualLayoutEditor`) permite configurarea vizuală a poziționării celor două texte pe ecran.

**Preset-urile disponibile**:

| Preset | Original | Traducere |
|---|---|---|
| Original sus / Traducere jos | x=0, y=0.05, w=1.0, h=0.50 | x=0, y=0.58, w=1.0, h=0.37 |
| Original jos / Traducere sus | x=0, y=0.55, w=1.0, h=0.40 | x=0, y=0.05, w=1.0, h=0.45 |
| Original stânga / Traducere dreapta | x=0.02, y=0.1, w=0.46, h=0.80 | x=0.52, y=0.1, w=0.46, h=0.80 |
| Traducere mică sub original | x=0, y=0.05, w=1.0, h=0.65 | x=0.05, y=0.73, w=0.90, h=0.22 |
| Side by side | x=0.01, y=0.05, w=0.48, h=0.90 | x=0.51, y=0.05, w=0.48, h=0.90 |

Toate valorile de layout sunt proporții din 0.0 la 1.0 față de dimensiunile ecranului.

**Valorile implicite ale layout-ului dual**:

```
original:
  x=0.0, y=0.0, width=1.0, height=0.55
  font_size=48, color=#ffffff, align=center, padding=20

translation:
  x=0.0, y=0.58, width=1.0, height=0.38
  font_size=32, color=#cccccc, align=center, padding=16
```

---

## 20. EDITORUL DE PREZENTĂRI GRAFICE

### 20.1 Prezentare generală

`PresentationEditor` este un editor de tip PowerPoint integrat în Cantio. Folosește `QGraphicsScene` și `QGraphicsView`. Permite crearea de slide-uri grafice cu multiple elemente.

Dimensiunea logică a canvas-ului: **1920×1080 px** (`CANVAS_W`, `CANVAS_H`).

### 20.2 Tipurile de elemente

| Tip | Constanta | Descriere |
|---|---|---|
| Text | `ET_TEXT = "text"` | Element de text formatat |
| Imagine | `ET_IMAGE = "image"` | Imagine din fișier |
| Dreptunghi | `ET_RECT = "rect"` | Formă dreptunghiulară |
| Elipsă | `ET_ELLIPSE = "ellipse"` | Formă eliptică / cerc |
| Linie | `ET_LINE = "line"` | Linie dreaptă |

### 20.3 Proprietățile unui element Text implicit

```
x=200, y=200, w=400, h=100, z=0
locked=false, visible=true
animation: entrance=none, delay=0, duration=500ms
text="Text nou"
font=Segoe UI, font_size=48pt
bold=false, italic=false, underline=false
color=#ffffff, align=center
bg_color="" (transparent), border_color=""
```

### 20.4 Proprietățile unui element Dreptunghi implicit

```
fill=#5294e2, border_color=#ffffff
border_width=2, opacity=1.0, border_radius=0
```

### 20.5 Proprietățile unui element Elipsă implicit

```
fill=#a6e3a1, border_color=#ffffff
border_width=2, opacity=1.0
```

### 20.6 Proprietățile unui element Linie implicit

```
color=#ffffff, line_width=3
w=400, h=0
```

### 20.7 Mânerele de redimensionare

Elementele selectate au 8 mânere de redimensionare de **10×10 px** (`HANDLE_SIZE = 10`), în culorile `#5294e2` (fill) și `#ffffff` (bordură), plasate la colțuri și pe mijlocul marginilor.

Cursoarele pentru mânere:
- `tl`, `br` → SizeFDiagCursor
- `tr`, `bl` → SizeBDiagCursor
- `t`, `b` → SizeVerCursor
- `l`, `r` → SizeHorCursor

### 20.8 Animațiile de intrare disponibile

`none, fade_in, slide_left, slide_right, slide_up, slide_down, zoom_in, bounce`

### 20.9 Setările implicite ale unui slide de prezentare

```json
{
    "bg_color": "#000000",
    "bg_image": "",
    "bg_gradient": null,
    "elements": [],
    "transition": "fade",
    "transition_ms": 300
}
```

### 20.10 Undo / Redo

Editorul de prezentări suportă undo/redo cu stivă de maxim **50** operații (`MAX_UNDO = 50`).

---

## 21. MODULUL MEDIA — FIȘIERE LOCALE, CAMERE, CLOUD

### 21.1 Structura tab-ului Media

Tab-ul Media are 3 sub-tab-uri:
1. **Local** — browser de fișiere media din folderele locale
2. **Feeds** — camere video live
3. **Cloud** — media din repository-ul GitHub `TudorSenegeac/cantio-media`

### 21.2 Formatele suportate

**Imagini**: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp`
**Video**: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`

### 21.3 Cache-ul media local

Fișierele descărcate din cloud se stochează în: `~/Cantio/media_cache/`
Durata de viață cache cloud: **3600 secunde** (1 oră)

### 21.4 Sursa media cloud

Repository GitHub: `TudorSenegeac/cantio-media` (branch `main`)
URL API: `https://api.github.com/repos/TudorSenegeac/cantio-media/git/trees/main?recursive=1`
URL fișiere: `https://raw.githubusercontent.com/TudorSenegeac/cantio-media/main/<cale>`

`CloudFetchThread` — QThread care descarcă lista fișierelor din API GitHub (timeout 10 s).

### 21.5 Detectarea camerelor

`CameraDetectThread` — QThread care testează camerele 0–7 (`MAX_CAMERAS = 8`). Pentru fiecare cameră găsită emite semnalul `camera_found(camera_idx, first_frame_or_None)`. La final emite `detection_done(total_count)`.

### 21.6 Camera live (CameraThread)

Fir dedicat pentru captură video:
- Setează `CAP_PROP_BUFFERSIZE = 1` pentru latență minimă
- Citește frame-uri la 30 fps (frame_time = 1/30 secundă)
- Redimensionează la 1920×1080 cu `INTER_LINEAR`
- Convertește BGR → RGB
- Emite frame-urile ca array numpy RGB
- `stop()` → setează `_running = False`, `quit()`, `wait(2000 ms)`

### 21.7 Cântări online (Online Songs Tab)

Tab-ul de cântări online permite căutarea în baza de date externă:
- API Base: `https://www.cantaricrestine.ro/api.php`
- URL Base: `https://www.resursecrestine.ro`
- Cache local: `online_cache.json` în directorul profilului
- Durata cache: **86400 secunde** (24 ore)
- Număr maxim de intrări în cache: **100**

---

## 22. NOTIFICĂRI, JURNAL ȘI UTILITARE INTERNE

### 22.1 Notificările Toast

Notificările pop-up non-blocante (`toast_notifications.py`) apar în colțul dreapta-jos al ferestrei de operator.

**Cele 4 tipuri și culorile lor**:

| Tip | Fundal | Text / bordură |
|---|---|---|
| `info` | `#1a3a5c` | `#5294e2` |
| `warning` | `#3d2e00` | `#e2a252` |
| `error` | `#3d0f0f` | `#e25252` |
| `success` | `#0f3d1a` | `#52e27a` |

**Dimensiuni**: lățime fixă 360 px, înălțime minimă 64 px, înălțime maximă 90 px.

**Timinguri**:
- Auto-dispariție după: **4000 ms**
- Animație slide-in: **250 ms** (easing OutCubic)
- Animație slide-out: **200 ms** (easing InCubic)

**Stacking**: maxim **3** notificări simultane. Marginea dintre ele: **12 px**. Marginea față de marginea ferestrei: 12 px.

### 22.2 Jurnalul aplicației

Jurnalele se scriu zilnic în `~/Cantio/logs/cantio_YYYYMMDD.log`.
- Format: `HH:MM:SS [NIVEL] Cantio: mesaj`
- Nivel fișier: DEBUG (toate mesajele)
- Nivel consolă: WARNING și mai grave
- Rotație automată: se păstrează maxim **7** fișiere de jurnal

### 22.3 Execuția asincronă a operațiunilor de baze de date

`AsyncDB` din `db_thread.py` permite apeluri non-blocante la baza de date:
- Folosește `QThreadPool` global
- Maxim **2** fire de execuție concurente pentru baza de date
- Callback-urile se execută pe firul principal (GUI) prin semnale Qt
- Fire pentru citiri → concurente; pentru scrieri → serializate de SQLite WAL

### 22.4 Cache-ul de pixmap-uri (PixmapCache)

`PixmapCache` din `pixmap_cache.py` implementează un cache LRU thread-unsafe (folosit doar pe firul principal):
- Capacitate maximă: **20** pixmap-uri
- La 1920×1080 px cu 32 bpp: ~8 MB per pixmap → limita totală ~160 MB
- Evicție: cel mai vechi pixmap (LRU = Least Recently Used)
- La evicție: delete explicit + `gc.collect()`
- Singleton global: `_global_cache = PixmapCache(max_size=20)`

### 22.5 Importul leneș al modulelor grele

`lazy_imports.py` amână importul modulelor costisitoare până la primul lor apel. Aceasta reduce timpul de pornire al aplicației de aproximativ **3 ori**.

Module importate leneș:

| Funcție | Modul importat |
|---|---|
| `get_cv2()` | `cv2` (OpenCV) |
| `get_flask()` | `flask` |
| `get_translator()` | `deep_translator.GoogleTranslator` |
| `get_fitz()` | `fitz` (PyMuPDF) |
| `get_docx()` | `docx` (python-docx) |
| `get_psutil()` | `psutil` |
| `get_reportlab_canvas()` | `reportlab.pdfgen.canvas` |

La importul `cv2`, variabilele de mediu `OPENCV_LOG_LEVEL=SILENT` și `OPENCV_VIDEOIO_DEBUG=0` sunt setate automat pentru a suprima mesajele de eroare ale OpenCV.

### 22.6 Utilitare pentru text (text_utils.py)

**`apply_sacred_caps(text, words, allcaps=False)`**:
- Identifică cuvintele sacre case-insensitiv cu regex `\bword\b`
- Le înlocuiește cu forma canonică (sau majuscule dacă `allcaps=True`)

**`wrap_text_to_fit(text, font_family, font_size, font_bold, font_italic, line_spacing, max_width, max_height, min_font_size=16)`**:
- Reduce dimensiunea fontului cu 1 pt la fiecare iterație (de la `font_size` până la `min_font_size`)
- Word-wrap: dacă o linie depășește `max_width`, se împarte în cuvinte
- Verifică că blocul total se încadrează în `max_height`
- Returnează `(wrapped_lines, final_size, font, fm)`
- La dimensiunea minimă, continuă cu word-wrap fără a mai reduce fontul

### 22.7 Ecranul de pornire (SplashScreen)

Dimensiunea ecranului splash: **900×506 px** (raport 16:9).
Imagini afișate: `SplashScreen.png` → `GPSPLASH-cutout.png`

Bara de progres:
- Înălțime: **4 px**
- Gradient de culoare: `#4d9fff` → `#a0c8ff`
- Pași de progres și timinguri:
  - La 15% progres: 450 ms
  - La 45% progres: 600 ms
  - La 75% progres: 550 ms

---

## 23. PORNIRE, INIȚIALIZARE ȘI CICLU DE VIAȚĂ AL APLICAȚIEI

### 23.1 Fișierul de intrare (main.py)

Versiunea aplicației: **1.0.0**
Font global: **Segoe UI 10pt** (setat pe `QApplication`)

Secvența de pornire:

1. `QApplication.setQuitOnLastWindowClosed(False)` — previne închiderea prematură la ascunderea ferestrelor
2. Se detectează și se setează limba interfeței (din setări sau implicit română)
3. Se afișează ecranul de pornire (`SplashScreen`)
4. Se afișează dialogul de selecție profil (`ProfileSelectDialog`)
5. Se inițializează baza de date (`database.init_db()`)
6. Se verifică dacă există baze de date vechi de migrat (`migration.check_and_migrate()`)
7. Se deschide fereastra principală de operator (`ControlWindow`)
8. Se pornește bucla evenimentelor Qt (`app.exec()`)

### 23.2 Inițializarea bazei de date

`database.init_db(profile)`:
1. Creează directorul profilului dacă nu există
2. Deschide conexiunea SQLite cu WAL mode
3. Creează tabelele dacă nu există (songs, settings, bible_books, bible_verses, bible_translations)
4. Creează/actualizează indexul FTS5
5. Aplică valorile implicite ale setărilor (dacă nu există în baza de date)
6. Rulează eventuale migrări de schemă (`migrate_slides_format()`)

### 23.3 Detectarea și pornirea procesului Electron

`ElectronDisplayManager` din `electron_display.py` gestionează procesul Electron:

1. La creare, caută executabilul în ordinea:
   - `CantioDisplay.exe` (în directorul aplicației)
   - `node_modules/electron/dist/electron.exe` (npm local)
   - `npx electron` / `electron.cmd` (instalare globală)

2. Pornește procesul Electron ca subprocess Python

3. Încearcă să conecteze WebSocket la `ws://localhost:7432`

4. Dacă conexiunea eșuează, încearcă din nou (reconnect automat)

5. La primirea mesajului `ready` de la Electron, procesul este considerat pregătit

### 23.4 ElectronDisplayProxy

`ElectronDisplayProxy` este un adaptor drop-in care expune același API ca fosta `DisplayWindow` PyQt. Metodele disponibile:

| Metodă | Acțiune |
|---|---|
| `show_text(text, settings)` | Afișează versuri pe proiector |
| `black_screen()` | Ecran negru |
| `apply_settings(settings)` | Aplică setări de temă |
| `set_ticker(text, speed, color)` | Pornește ticker |
| `toggle_clock(visible, color, fmt)` | Afișează/ascunde ceas |
| `start_countdown(seconds, color)` | Pornește countdown |
| `freeze_display()` | Înghețare afișaj |
| `unfreeze_display()` | Dezghețare afișaj |
| `show_logo(path)` | Afișează logo |
| `projector_off()` | Oprire proiector |
| `clear_text()` | Șterge textul de pe ecran |
| `show_slide_image(path)` | Afișează imagine pe ecran |
| `toggle_transparent(value)` | Comutare transparent |

### 23.5 Localizarea interfeței (translations.py)

5 limbi disponibile:
- **ro** — Română (limba implicită și fallback)
- **en** — English
- **de** — Deutsch
- **fr** — Français
- **hu** — Magyar

Funcții principale:
- `t(key)` — returnează textul în limba curentă; dacă cheia nu există, returnează varianta română
- `set_language(lang)` — schimbă limba curentă
- `get_language()` — returnează codul limbii curente
- `available_languages()` — returnează dicționarul `{cod: nume}` al limbilor disponibile

### 23.6 Închiderea aplicației

La ieșire:
1. Procesul Electron primește comanda `quit` prin WebSocket
2. Electronul închide serverul WebSocket
3. Toate ferestrele Qt se închid
4. Baza de date SQLite se închide (WAL checkpoint automat)
5. Jurnalul se finalizează

### 23.7 Tutorialul interactiv

La prima rulare (sau la cerere), se declanșează `InteractiveTutorial`. Pașii tutorialului:

| Pas | Titlu | Element UI indicat |
|---|---|---|
| 1 | Welcome | (general) |
| 2 | Căutare Cântări | Câmpul de căutare |
| 3 | Lista de Cântări | Lista de cântări |
| 4 | Serviciu | Panoul de serviciu |
| 5 | Slide-uri | Grila de miniaturi |
| 6 | GO LIVE | Butonul GO LIVE |
| 7 | Preview Output | Widgetul de previzualizare |

Fiecare pas are: titlu, text explicativ, atributul widget-ului țintă, acțiunea care avansează la pasul următor, și direcția săgeții de indicare.

### 23.8 Dialogul „Despre Cantio" (AboutDialog)

Dimensiunea dialogului: **520×560 px**. Fundalul: `#11111b`.

Tab-uri disponibile:
1. **Despre** — logo, versiune, descriere scurtă
2. **Licență GPL-3.0** — textul complet al licenței GNU GPL v3
3. **Termeni și Condiții** — termenii de utilizare (text custom)
4. **Credite** — lista contribuitorilor și bibliotecilor utilizate

Header-ul dialogului: înălțime fixă 130 px, fundal `#1e1e2e`. Logo: 90×90 px.

Tab-ul selectat: culoare accent `#cba6f7`, bordura de jos 2 px `#cba6f7`.
Tab-uri neselecionate: text `#6c7086`, fără bordură.

Butonul „Închide": fundal `#a6e3a1`, text `#1e1e2e`, hover `#94e2d5` (verde → turcoaz).

Informații din „Credite":
- Dezvoltator principal: Tudor Senegeac (@TudorSenegeac)
- Biblioteci: PyQt6 (GPL-3.0), Electron (MIT), Node.js (MIT), OpenCV (Apache-2.0), SQLite3 (public domain), requests (Apache-2.0)
- Design inspirat din: FreeShow, ProPresenter, EasyWorship

---

## ANEXĂ A — VALORILE EXACTE ALE PARAMETRILOR CRITICI

### A.1 Timinguri și intervale

| Parametru | Valoare | Locație |
|---|---|---|
| Debounce căutare | 250 ms | control_window.py (SongsModel) |
| Interval animație display | 16 ms | display.js |
| Interval ticker | 16 ms | live_state.py, display.js |
| Interval ceas | 500 ms | live_state.py |
| Interval countdown | 1000 ms | live_state.py |
| Fade-in deschidere ecran | 500 ms easeOutCubic | main.js (Electron) |
| Delay fullscreen după show | 200 ms | main.js (Electron) |
| Fade-out închidere ecran | 0.08/16ms (≈~200ms) | main.js (Electron) |
| Delay recreare fereastră (set_transparent) | 350 ms | main.js (Electron) |
| Splash paso 15% | 450 ms | splash_screen.py |
| Splash paso 45% | 600 ms | splash_screen.py |
| Splash paso 75% | 550 ms | splash_screen.py |
| Auto-dispariție toast | 4000 ms | toast_notifications.py |
| Slide-in toast | 250 ms OutCubic | toast_notifications.py |
| Slide-out toast | 200 ms InCubic | toast_notifications.py |
| Interval render preview | 67 ms (15 fps) | render_engine.py |
| Interval render display | 16 ms (60 fps) | render_engine.py |
| Camera target fps | 30 fps | media_engine.py, media_tab.py |

### A.2 Dimensiuni și rezoluții

| Parametru | Valoare | Locație |
|---|---|---|
| Canvas display full-res | 1920×1080 px | renderer.py, presentation_editor.py |
| Preview | 320×180 px | render_engine.py |
| Thumb XS | 120×68 px | control_window.py |
| Thumb S (implicit) | 168×94 px | control_window.py |
| Thumb M | 220×124 px | control_window.py |
| Thumb L | 300×169 px | control_window.py |
| Thumb XL | 400×225 px | control_window.py |
| Bara miniatură (jos) | 22 px înălțime | control_window.py |
| Mânere resize | 10×10 px | presentation_editor.py |
| Fereastra About | 520×560 px | about_dialog.py |
| Header About | 130 px înălțime | about_dialog.py |
| Logo About | 90×90 px | about_dialog.py |
| Splash screen | 900×506 px | splash_screen.py |
| Preview temă 16:9 | 320×180 px | theme_editor.py |
| Preview temă 4:3 | 320×240 px | theme_editor.py |
| Preview temă 21:9 | 320×137 px | theme_editor.py |
| Toast lățime | 360 px | toast_notifications.py |
| Toast înălțime min | 64 px | toast_notifications.py |
| Toast înălțime max | 90 px | toast_notifications.py |
| ColorButton | 48×28 px | settings_dialog.py |

### A.3 Porturile rețelei

| Serviciu | Port |
|---|---|
| Electron WebSocket | 7432 |
| Flask server mobil | 5050 |

### A.4 Praguri și limite

| Parametru | Valoare | Locație |
|---|---|---|
| PAGE_SIZE (paginare cântări) | 200 | control_window.py |
| MAX_UNDO (editor prezentări) | 50 | presentation_editor.py |
| Pixmap cache max entries | 20 | pixmap_cache.py |
| Log files păstrate | 7 | logger.py |
| Recent services | 5 | service_manager.py |
| Import history | 50 | import_manager.py |
| Online cache max entries | 100 | online_songs_tab.py |
| Online cache TTL | 86400 s (24h) | online_songs_tab.py |
| Cloud media cache TTL | 3600 s (1h) | media_tab.py |
| Camera detection max | 8 (index 0–7) | media_tab.py |
| Camera stop wait | 2000 ms | media_tab.py |
| AsyncDB max threads | 2 | db_thread.py |
| Font size min display | 10 px | display.js |
| Font size min render (full-res) | 20 px | renderer.py |
| Font size min render (scaled) | `20 × scale` | renderer.py |
| Smart paste line threshold | >3 linii | control_window.py |
| Smart paste long line | >80 caractere | control_window.py |
| Password min length | 4 caractere | profile_manager.py |
| Max toast simultane | 3 | toast_notifications.py |
| Toast margin | 12 px | toast_notifications.py |
| Copy buffer migration | 256 KB | migration.py |

### A.5 Culorile exacte ale interfeței

| Element | Culoare |
|---|---|
| Fundal fereastra operator | `#11111b` |
| Fundal panouri | `#1e1e2e` |
| Fundal intrări text | `#1c1c1c` |
| Text principal | `#cdd6f4` |
| Text secundar | `#a6adc8` |
| Borduri normale | `#313244` |
| Borduri hover | `#45475a` |
| Accent albastru | `#89b4fa` |
| Accent violet | `#cba6f7` |
| Accent verde | `#a6e3a1` |
| Accent roșu | `#f38ba8` |
| Accent turcoaz | `#94e2d5` |
| Accent portocaliu | `#fab387` |
| Accent galben | `#f9e2af` |
| Slide selectat (fundal) | `#1c3a5a` |
| Slide selectat (bordură) | `#5294e2` |
| Slide hover (fundal) | `#1e1e1e` |
| Slide normal (fundal) | `#141414` |
| Badge număr slide selectat | `#5294e2` |
| Badge număr slide normal | `#2a2a2a` |
| Note operator (fundal) | `#1a1a0a` |
| Note operator (text) | `#ccaa44` |
| Note operator (bordură) | `#3a3010` |
| Bara progres splash | `#4d9fff` → `#a0c8ff` |
| Bara progres migrare | `#5294e2` |
| Timer culoare verde | `#00ff88` |
| Ticker bg implicit | `#000000cc` |
| Toast info (fundal) | `#1a3a5c` |
| Toast info (bordură) | `#5294e2` |
| Toast warning (fundal) | `#3d2e00` |
| Toast warning (bordură) | `#e2a252` |
| Toast error (fundal) | `#3d0f0f` |
| Toast error (bordură) | `#e25252` |
| Toast success (fundal) | `#0f3d1a` |
| Toast success (bordură) | `#52e27a` |

---

## ANEXĂ B — FORMULELE MATEMATICE ALE ANIMAȚIILOR

### B.1 easeOutCubic (fade-in ecran)

```javascript
eased = 1 - Math.pow(1 - progress, 3)
```

Unde `progress` = (milisecunde_scurse / 500) clamped la [0, 1].
Această funcție pornește rapid și încetinește spre final, producând o apariție naturală a ferestrei.

### B.2 Scalarea coordonatelor (renderer.py)

```python
scale = widget_width / 1920.0
font_size  = max(4, int(font_size_fr  * scale))
outline_w  = max(0, int(outline_w_fr  * scale))
margin     = max(2, int(margin_fr     * scale))
```

Toate dimensiunile sunt specificate în coordonate la rezoluția completă 1920×1080 și scalate proporțional la rezoluția reală a widget-ului.

### B.3 Reducerea automată a fontului (text_utils.py)

```python
for size in range(font_size, min_font_size - 1, -1):
    # calculează wrap
    # verifică dacă se încadrează
    if total_h <= max_height and max_w <= max_width:
        return wrapped, size, font, fm
```

Reduce cu câte 1 pt de la dimensiunea specificată până la dimensiunea minimă. Dacă nici la minimum nu se încadrează, returnează tot cu font-ul minimum.

### B.4 Detectarea ecranelor (main.js)

```javascript
if (screenIdx === 0 && secondaryDisplays.length > 0) {
    targetDisplay = secondaryDisplays[0];
} else if (screenIdx > 0 && screenIdx <= secondaryDisplays.length) {
    targetDisplay = secondaryDisplays[screenIdx - 1];
} else {
    targetDisplay = displays[Math.min(screenIdx, displays.length - 1)];
}
```

Indexarea `screen_index = 0` înseamnă „primul ecran NON-primar". Indexarea `screen_index = 1` înseamnă „al doilea ecran secundar" (1-based), compatibil cu setarea „Screen 1" din interfață.

---

## ANEXĂ C — STRUCTURA MESAJELOR WEBSOCKET

### C.1 Mesaj show_text (Python → Electron)

```json
{
    "type": "show_text",
    "window_id": 1,
    "text": "Versetul sau versul de afișat",
    "title": "Titlul cântării",
    "author": "Autorul",
    "slide_index": 2,
    "slide_count": 5,
    "settings": {
        "font_family": "Arial",
        "font_size": 48,
        "font_bold": "true",
        "text_color": "#ffffff",
        "outline_color": "#000000",
        "outline_width": 2,
        "bg_color": "#000000",
        "margin": 60,
        "line_spacing": 1.4,
        "text_align": "center",
        "text_valign": "center",
        "transition": "crossfade"
    }
}
```

### C.2 Mesaj ticker (Python → Electron)

```json
{
    "type": "ticker",
    "window_id": 1,
    "text": "Textul care derulează în ticker",
    "speed": 3,
    "color": "#ffffff",
    "bg_color": "#000000cc",
    "height": 40,
    "position": "bottom"
}
```

### C.3 Mesaj timer (Python → Electron)

```json
{
    "type": "timer",
    "window_id": 1,
    "seconds": 300,
    "color": "#00ff88"
}
```

### C.4 Mesaj clock (Python → Electron)

```json
{
    "type": "clock",
    "window_id": 1,
    "visible": true,
    "color": "#ffffff",
    "format": "HH:MM:SS",
    "position": "top_right"
}
```

### C.5 Mesaj open (Python → Electron)

```json
{
    "type": "open",
    "window_id": 1,
    "screen_index": 0,
    "window_name": "Display 1",
    "transparent": false
}
```

### C.6 Răspuns ready (Electron → Python)

```json
{
    "type": "ready",
    "screens": [
        {
            "index": 0,
            "id": 12345,
            "label": "\\\\.\\ DISPLAY1",
            "name": "Primary",
            "bounds": {"x": 0, "y": 0, "width": 1920, "height": 1080},
            "width": 1920,
            "height": 1080,
            "x": 0,
            "y": 0,
            "primary": true,
            "scaleFactor": 1.25,
            "screen_index": 0
        }
    ]
}
```

---

*Document generat pe baza codului sursă al aplicației Cantio versiunea 1.0.0.*
*Toate valorile sunt exacte conform codului sursă analizat.*

---

## ANEXĂ D — DETALII EXTINSE ALE DIALOGULUI DE SETĂRI

### D.1 Tab-ul Display (Afișaj)

Tab-ul Display din `SettingsDialog` este primul tab și conține:

**Grupul Mod personalizare afișare**:
- Radio „⚙ Setări globale (clasic)" — fontul, culoarea etc. din Settings se aplică la toate cântările uniform
- Radio „🎨 Teme personalizate" — permite personalizare avansată per gen, per cântare sau per tip (cântări/biblie)
- Text explicativ gri `#6c7086`, font 11px, cu word-wrap

**Grupul Monitor / Screen**:
- Dropdown cu lista ecranelor detectate automat
- Format: `Screen {nr}: {nume} ({lățime}×{înălțime})`
- Valoarea selectată se salvează ca `screen_index`

**Grupul Background**:
- ColorButton culoare solidă `bg_color`
- Câmp imagine: label cu calea + butoane Browse / Clear
- Slider opacitate imagine: 0–100 (se stochează ca float 0.0–1.0)
- Câmp video: label cu calea + butoane Browse / Clear (formate: MP4, MOV)

**Grupul Transition**:
- Dropdown cu efectele: `fade`, `crossfade`, `slide_left`, `zoom_in`, `instant`
  - `fade` = fade out → swap → fade in
  - `crossfade` = dissolve (vechi dispare simultan cu apariția celui nou)
  - `slide_left` = vechiul iese stânga, noul intră din dreapta
  - `zoom_in` = noul se scalează de la mic la normal + fade
  - `instant` = fără animație
- SpinBox durată tranziție: 50–2000 ms, pas 50 ms, implicit **350 ms**
  - Tooltip: „50 ms = aproape instant / 350 ms = implicit / 1000 ms = lent"

### D.2 Tab-ul Text

**Grupul Font**:
- `QFontComboBox` pentru familia fontului
- `QSpinBox` dimensiune: **12–200 pt**
- `QCheckBox` Bold, `QCheckBox` Italic

**Grupul Color & Effects**:
- ColorButton culoare text (implicit `#ffffff`)
- Checkbox Drop shadow (umbra textului)
- Linie outline: ColorButton culoare contur + SpinBox lățime (0–10)
- SpinBox Line spacing: 1.0–3.0, pas 0.1, 1 zecimală
- SpinBox Margin: 0–400 px

**Grupul Alignment**:
- Dropdown orizontal: `center`, `left`, `right`
- Dropdown vertical: `center`, `top`, `bottom`

**Grupul Cuvinte cu majuscule automate**:
- Checkbox „Activează capitalizare automată pentru cuvinte sacre"
- Checkbox „MAJUSCULE COMPLETE (ex: ISUS, ALELUIA)"
- `QTextEdit` (120 px înălțime) pentru lista de cuvinte (câte unul pe linie sau separate prin virgulă)
- Buton „Resetează la valorile implicite" (220 px lățime) → resetează la lista implicită de cuvinte sacre

### D.3 Tab-ul Overlays

**Grupul Ticker / Alert Scroll**:
- Checkbox „Enable ticker at bottom of screen"
- Câmp text ticker (QLineEdit cu placeholder)
- ColorButton culoare text ticker (implicit `#ffffff`)
- SpinBox viteză: **1–10** (implicit 2)

**Grupul Live Clock**:
- Checkbox „Show live clock (top-right of screen)"
- ColorButton culoare ceas (implicit `#ffffff`)
- Dropdown format: `HH:MM:SS`, `HH:MM`, `12h`

**Grupul Countdown Timer**:
- Checkbox „Show countdown timer (top-center of screen)"
- SpinBox durată: **10–7200 secunde** (implicit 300 = 5 minute)
- ColorButton culoare timer (implicit `#ffffff`)

### D.4 Tab-ul Ferestre (Windows)

Permite configurarea ferestrelor de afișare multiple. Fiecare fereastră poate fi configurată cu un ecran țintă diferit.

### D.5 Tab-ul Interface Language

Permite schimbarea limbii interfeței. La schimbare, se afișează un mesaj că aplicația trebuie repornită pentru a aplica limba nouă.

### D.6 Tab-ul Cloud (Supabase)

Câmpuri pentru integrarea Supabase:
- URL proiect Supabase
- Cheia API (anon key)
- Bucket-ul de stocare
- Buton „Test conexiune"

### D.7 Tab-ul Backup

Permite:
- Export baza de date ca JSON
- Import baza de date din JSON
- Creare backup manual la o cale specificată
- Backup automat (perioadă configurabilă)

### D.8 Tab-ul Baza de date

Afișează statistici despre baza de date:
- Numărul total de cântări
- Dimensiunea fișierului .db
- Buton „Compactare" (VACUUM SQLite)
- Buton „Reindexare FTS5"

### D.9 Tab-ul Securitate

Include:
- Tab-ul de setări profil (`ProfileSettingsTab`)
- Configurarea parolei profilului curent
- Activarea/dezactivarea restricțiilor (no_delete_songs, no_import, etc.)

### D.10 Previzualizarea live în dialog

Panoul dreapta al dialogului de setări conține o previzualizare live (`PreviewWidget`) care se actualizează în timp real la orice modificare.

Dimensiunile splitter-ului: tab-uri stânga 520 px / preview dreapta 300 px (setate explicit la `[520, 300]`).

Textele de probă disponibile (selector dropdown):
1. „Doamne, Tu ești lumina mea / Și mântuirea mea"
2. „Aleluia! Slavă Celui / Care a murit și-a înviat"
3. „Isuse, Isuse / Nume mai presus de orice nume"
4. „Sfânt, sfânt, sfânt / Este Domnul Dumnezeu Atotputernic"

---

## ANEXĂ E — MINI PLAYER VIDEO ȘI TRIMITERE MEDIA LIVE

### E.1 MiniVideoPlayer

Widget compact integrat în fereastra principală de operator (înălțime minimă: **170 px**).

**Componente**:
- Label titlu „🎬 Media Player" (culoare `#cba6f7`, 11px bold)
- `QVideoWidget` (înălțime minimă: 120 px, fundal `#000000`, border-radius 6px)
- `QMediaPlayer` cu `QAudioOutput` (volum implicit: 0.7 = 70%)

**Bare de control**:
- Buton ▶ (Play/Pause, 30 px lățime)
- Buton ⏹ (Stop, 30 px lățime)
- Slider progres (orizontal, range 0–1000)
- Slider volum (orizontal, 55 px lățime, range 0–100, implicit 70)

**Butoane suplimentare**:
- „📺 Send Live" — trimite fișierul media curent ca fundal pe proiector; fundal `#313244`, bordură `#a6e3a1`, text verde
- „🔁 Loop" — repeat; buton checkable (toggle), când activ: fundal `#45475a`, text `#cba6f7`

**Fallback**: Dacă `PyQt6-Qt6-Multimedia` nu este instalat, widget-ul afișează un mesaj de indisponibilitate și butoanele media sunt dezactivate.

### E.2 Trimiterea unui fișier media ca fundal live

Când operatorul apasă „Send Live" în MiniVideoPlayer sau din tab-ul Media:
1. Calea fișierului se trimite la ElectronDisplayProxy
2. Se trimite comanda `slide_image` sau `show_slide_image` pe WebSocket
3. Ecranul Electron afișează imaginea/video-ul ca strat de conținut
4. Setările curente de text rămân active (textul se suprapune peste imagine/video)

---

## ANEXĂ F — DIALOGUL DE IMPORT CU SELECȚIE CATEGORIE

### F.1 _ImportCategoryDialog

Dialog afișat înainte de importul de cântări (dimensiune minimă: 420 px lățime).

**Câmpuri**:
- Label cu numărul de cântări care vor fi importate
- `QComboBox` editabil cu categorii (combinare categorii implicite + categorii din baza de date, fără duplicate)
- `QCheckBox` „Păstrează categoria din fișier (dacă există)" — bifat implicit
- Câmp text „Sau creează categorie nouă"
- Label preview „Categorie din fișier sau: {cat}" (culoare `#a6e3a1`, bold)

**Categoriile implicite în dialog**:
`General, Imnuri, Psalmi, Colinde, Copii, Tineret, Laudă și Închinare, Rugăciune, Speciale`

**Logica categoriei**:
- Dacă există text în câmpul „categorie nouă" → se folosește acea categorie
- Altfel → se folosește categoria selectată din dropdown

---

## ANEXĂ G — RANDAREA TEXTULUI ÎN DETALIU (render_engine.py)

### G.1 Ordinea de randare a unui frame de preview

`RenderWorker._render()` execută în ordine:

1. **Fundal culoare** — `fillRect` cu `bg_color` pe întreaga suprafață
2. **Frame video** (numpy RGB → `QImage.Format_RGB888`) — scalat cu `IgnoreAspectRatio` și `FastTransformation` (rapidă), opacitate din `bg_opacity`
3. **Imagine statică** (`QImage`) — la fel, cu opacitate din `bg_opacity` (implicit 0.85 pentru imagine)
4. **Text versuri** — prin `_draw_text()` cu word-wrap și auto-shrink

### G.2 Word-wrap în render_engine.py

Algoritmul:
```
for raw_line in text.splitlines():
    if line empty → append ""
    for word in raw_line.split():
        test = current + " " + word
        if fm.horizontalAdvance(test) > max_w:
            append current, current = word
        else:
            current = test
    append current if non-empty
```

### G.3 Auto-shrink în render_engine.py

Pornind de la `font_size` scalat, se reduce cu **2 pt** la fiecare iterație (`size -= 2`) cât timp `total_h > max_h` și `size > 10`.

Diferența față de `text_utils.wrap_text_to_fit()`:
- `render_engine.py` scade cu 2 pt
- `text_utils.py` scade cu 1 pt (mai precis)
- Ambele au minimum 10 pt (display.js) sau 16 pt (text_utils implicit)

### G.4 Umbra textului

În `render_engine.py`, umbra se desenează cu offset calculat ca `max(1, int(3 * scale))` și culoarea `QColor(0, 0, 0, 180)` (negru cu ~70% opacitate).

### G.5 Conturul textului în render_engine.py

Conturul se desenează iterând toți pixelii din `(-outline_w, -outline_w)` până la `(+outline_w, +outline_w)` pentru fiecare linie, excluzând originea (dx=0, dy=0). Aceasta produce un contur gros pe toate direcțiile.

### G.6 Alinierea verticală

| Valoare | Formula start_y |
|---|---|
| `top` | `margin + fm.ascent()` |
| `bottom` | `h - margin - total_h + fm.ascent()` |
| `center` (implicit) | `(h - total_h) // 2 + fm.ascent()` |

`start_y` este clamped la minimum `margin + fm.ascent()` pentru a nu depăși marginile.

### G.7 Alinierea orizontală

| Valoare | Formula x |
|---|---|
| `left` | `margin` |
| `right` | `w - margin - lw` (lw = lățimea liniei) |
| `center` (implicit) | `(w - lw) // 2` |

`x` este clamped în intervalul `[margin, w - margin - lw]`.

---

## ANEXĂ H — COMUNICAREA PYTHON ↔ ELECTRON ÎN DETALIU

### H.1 Ciclul de viață al conexiunii WebSocket

```
Python start → pornire subprocess Electron
              → Electron creează server WS pe port 7432
              → Electron trimite {"type": "ready", "screens": [...]}
              → Python primește "ready" → conexiune stabilă

Normal operation:
  Python → ws.send(JSON command)
  Electron → ws.send({"type": "ok", "window_id": X})

Disconnect detection:
  Python detectează ws.close() → reconnect automat
```

### H.2 Gestionarea erorilor WebSocket

- Mesajele care nu pot fi parsate ca JSON sunt ignorate silențios
- Evenimentele `error` și `close` pe conexiunile WebSocket sunt capturate silențios (no-op handlers)
- Procesul Electron ignoră erorile EPIPE, ERR_STREAM_DESTROYED, ERR_STREAM_WRITE_AFTER_END pe stdout/stderr

### H.3 Broadcast vs. unicast

**Unicast** (window_id specificat):
```javascript
if (windowId !== undefined && windowId !== null) {
    const win = windows.get(windowId);
    if (win) send(win);
}
```

**Broadcast** (window_id = null/undefined):
```javascript
windows.forEach((win) => send(win));
```

### H.4 Mecanismul dual de trimitere

`broadcast()` folosește două căi simultan:
1. `win.webContents.send('render', msg)` — IPC principal (Electron IPC)
2. `win.webContents.executeJavaScript(...)` — fallback dacă IPC-ul nu funcționează

Renderer-ul (`display.js`) ascultă pe ambele:
- `ipcRenderer.on('render', handler)` pentru IPC
- `window._handleRender = handler` pentru executeJavaScript

### H.5 Răspunsurile comenzilor

Fiecare comandă primeste un răspuns:
- Succes: `{"type": "ok", "window_id": X}`
- Eroare: `{"type": "error", "message": "Unknown command: X"}`
- Ping: `{"type": "pong", "resp": "pong"}`
- Screens: `{"type": "screens", "screens": [...]}`

---

## ANEXĂ I — FEREASTRA DE AFIȘARE LOCALĂ (display_window.py)

Cantio are două implementări pentru ecranul de proiecție:
1. **ElectronDisplayProxy** — utilizat în producție (fereastra Electron)
2. **DisplayWindow** + **DisplayCanvas** — implementare PyQt6 pură (fallback)

### I.1 DisplayCanvas

`DisplayCanvas` este un `QWidget` care randează totul direct în `paintEvent()`. Starea sa este complet independentă de `PreviewWidget` și `SlideThumbnail`.

**Starea internă**:
- `settings` — dicționar cu setările curente de temă
- `lyrics_text` — textul versurilor afișat curent
- `_bg_pixmap` — pixmap-ul imaginii de fundal
- `_video_frame` — array numpy RGB (frame video curent)
- `_pres_pix` — pixmap slide prezentare
- `_show_pres` — dacă se afișează prezentare

**Tranziția textului** (animație proprie):
- `_progress` — progres tranziție (0.0 → 1.0)
- `_transition` — tipul tranziției (implicit: `crossfade`)
- `_elapsed` — ms trecuți
- `_duration` — durata (din `_TRANSITION_DURATIONS`)
- Timer animație: interval **16 ms**, callback `_anim_step()`

**Duratele tranziției** (definite în `display_window.py`):
- `fade` → 500 ms
- `crossfade` → 350 ms
- `slide_left` → 350 ms
- `zoom_in` → 400 ms

**Overlay-uri proprii**:
- `ticker_text`, `ticker_active`, `_ticker_x`, `_ticker_speed` (implicit 2.5)
- `show_clock`, `show_timer`, `_timer_seconds`, `_timer_running`, `_timer_start`
- `logo_active`, `_logo_pixmap`, `projector_off`
- Timer ticker: interval **16 ms**, callback `_tick()`

### I.2 Stub-urile de compatibilitate

`display_window.py` definește stub-uri goale pentru componente care existau în versiuni anterioare:
- `LyricsWidget` — stub, randarea a trecut la DisplayCanvas
- `TickerBar` — stub, ticker condus de DisplayCanvas
- `ClockOverlay` — stub, ceas condus de DisplayCanvas
- `CountdownOverlay` — stub, countdown condus de DisplayCanvas

Aceste stub-uri există pentru a nu sparge codul din `control_window.py` care le referențiază ca atribute.

---

## ANEXĂ J — SUPABASE ȘI CLOUD STORAGE

### J.1 Integrarea Supabase

`cloud_manager.py` oferă integrare cu Supabase pentru stocarea fișierelor media în cloud. Necesită configurare:
- URL proiect Supabase
- Cheia anon
- Numele bucket-ului

Cache local la: `~/Cantio/cache/cloud/`

### J.2 Operațiile cloud disponibile

- `upload_file(local_path, remote_name)` — încarcă un fișier
- `list_files(prefix)` — listează fișierele dintr-un folder virtual
- `download_file(remote_name, local_path)` — descarcă un fișier

Toate operațiile folosesc biblioteca `requests` (importată direct, nu lazy).

---

## ANEXĂ K — FEREASTRA DE PREVIEW ÎN DETALIU (preview_widget.py)

### K.1 Funcția render_text_on_painter

Această funcție din `preview_widget.py` este utilizată atât de `PreviewWidget` cât și de `SlideThumbnail` pentru a desena textul pe un QPainter. Aplică aceleași reguli de word-wrap și scalare proporțională ca și display-ul principal.

### K.2 Smart word-wrap în preview_widget.py

Preview widget implementează word-wrap „smart" cu caracteristici avansate:
- **Echilibrare**: algoritmul încearcă să producă rânduri de lungimi apropiate (nu un rând scurt și altul lung)
- **Token-uri atomice la liniuță**: cuvintele cu liniuță (ex. „Dumnezeu-Tatăl") nu se împart la liniuță
- **Recompense pentru punctuație**: sfârșitul natural al unei fraze nu se penalizează
- **Penalizare rând singur**: un rând cu un singur cuvânt este evitat (se încearcă mutarea unui cuvânt)

### K.3 Metoda update_text

`PreviewWidget.update_text(text)` actualizează textul afișat în preview. Triggers un repaint la intervalul de 67 ms (15 fps).

### K.4 Metoda apply_settings

`PreviewWidget.apply_settings(settings)` aplică noile setări de temă (font, culori, margini etc.). Declanșează un repaint imediat.

---

## ANEXĂ L — STRUCTURA COMPLETĂ A UNUI ITEM DE SERVICIU

Un item din lista de serviciu conține minimum:

```json
{
    "type": "song",
    "id": 42,
    "title": "Titlul cântării",
    "author": "Autorul",
    "category": "Adorare",
    "language": "ro",
    "content": "Textul complet...",
    "slides": ["Slide 1 text", "Slide 2 text"],
    "notes": "Note interne operator",
    "settings": {},
    "theme": null,
    "slide_index": 0
}
```

Tipurile posibile ale unui item: `song`, `bible_verse`, `presentation`, `media`, `custom_text`

---

## ANEXĂ M — KEYBOARD SHORTCUTS — DETALII COMPLETE

### M.1 Definirea shortcut-urilor (keyboard_shortcuts.py)

Lista `SHORTCUTS` conține 13 intrări, fiecare cu:
- `keys` — secvența de taste (ex. `Ctrl+F`)
- `action` — codul acțiunii interne
- `description` — descrierea în limba curentă
- `category` — categoria (Navigation / Windows / Service / App)

### M.2 Dialogul ShortcutsDialog

Afișează scurtăturile într-un tabel cu color-coding per categorie:
- Navigation — fundal albastru
- Windows — fundal verde
- Service — fundal portocaliu
- App — fundal violet

### M.3 Implementarea navigării cu săgeți

Săgețile ←/→ pentru navigare slide-uri funcționează astfel:
1. `keyPressEvent` din fereastra principală captează evenimentul
2. Dacă focus-ul nu este pe un câmp text editabil → se procesează
3. ← → slide anterior din cântarea curentă
4. → → slide următor din cântarea curentă
5. Dacă suntem la ultimul/primul slide → rămâne pe loc (nu trece la cântarea următoare)
6. ↑/↓ → itemul anterior/următor din lista de serviciu (schimbă cântarea)

---

## ANEXĂ N — INTERFAȚA DE CONTROL MOBIL — DETALII

### N.1 Pagina web principală (/)

Interfața web pentru telefon/tabletă servită de Flask pe portul 5050. Afișează:
- Starea live (ce se afișează pe proiector)
- Lista itemilor din serviciu
- Butoane de navigare (slide anterior/următor)
- Buton GO LIVE / Ecran negru
- Câmp de căutare rapidă cântări

### N.2 Actualizarea stării în timp real

SocketIO (Flask-SocketIO) trimite actualizări push la client ori de câte ori starea se schimbă. Clientul web actualizează interfața fără a reîncărca pagina.

### N.3 Acțiunile disponibile din interfața mobilă

- Selectare item din serviciu
- Navigare slide anterior/următor
- Trimitere live a unui slide
- Ecran negru
- Afișare/ascundere ticker
- Afișare/ascundere ceas

---

## ANEXĂ O — SISTEMUL DE OVERLAY-URI AVANSATE (overlay_tab.py)

### O.1 Tipurile de overlay

`overlay_tab.py` definește un sistem mai avansat de overlay-uri față de ticker/ceas/timer din `overlay_settings.py`. Tipurile `OVERLAY_TYPES`:

| Tip | Descriere |
|---|---|
| `text` | Bloc de text pozicionabil |
| `image` | Imagine pozicionabilă |
| `shape` | Formă (dreptunghi/elipsă) |
| `ticker` | Ticker rulant |
| `countdown` | Countdown pozicionabil |
| `clock` | Ceas pozicionabil |
| `logo` | Logo pozicionabil |

### O.2 Structura unui OverlayItem

Fiecare overlay are:
- `id` — 8 caractere hexazecimale (UUID scurt)
- `name` — eticheta operatorului
- `otype` — tipul din OVERLAY_TYPES
- `visible` — dacă este afișat (true/false)
- `x`, `y` — poziția în procente din dimensiunea ecranului (0.0–1.0)
- `width`, `height` — dimensiunile în procente (0.0–1.0)
- `z_index` — ordinea de suprapunere (0 = fundal, valori mari = deasupra)
- `settings` — dicționar cu setările specifice tipului

---

## ANEXĂ P — DETALII ALE SISTEMULUI DE TEME

### P.1 Structura unui obiect de temă

O temă este stocată ca JSON și conține:
```json
{
    "name": "Tema Mea",
    "type": "songs",
    "font_family": "Arial",
    "font_size": 48,
    "font_bold": true,
    "font_italic": false,
    "text_color": "#ffffff",
    "outline_color": "#000000",
    "outline_width": 2,
    "text_shadow": true,
    "bg_color": "#000000",
    "bg_type": "gradient",
    "bg_grad_c1": "#000033",
    "bg_grad_c2": "#000000",
    "bg_grad_dir": "Sus→Jos",
    "bg_image": "",
    "bg_opacity": 0.5,
    "margin": 60,
    "line_spacing": 1.4,
    "text_align": "center",
    "text_valign": "center",
    "transition": "crossfade",
    "sacred_words_enabled": false,
    "sacred_words": []
}
```

### P.2 Aplicarea unei teme

Când operatorul apasă „Setează ca implicit" pe o temă:
1. Setările temei suprascriu `settings.json` al profilului curent
2. `ElectronDisplayProxy.apply_settings(settings)` trimite setările pe WebSocket
3. Ecranul Electron actualizează vizual (fundal, fonturi, culori)
4. Previzualizarea din fereastra operator se actualizează

### P.3 Drag-and-drop temă pe cântare

`ThemesGrid` suportă drag-and-drop: operatorul poate trage o temă de pe card și o poate dropa pe o cântare din lista de serviciu. Aceasta aplică tema doar la acea cântare (stocată în câmpul `formatting` sau `theme` al cântării).

### P.4 Tema de backup (fallback)

Dacă nicio temă nu este setată, se folosesc setările globale din `settings.json`. Dacă nici acelea nu există, se folosesc valorile implicite definite în `database.py`.

---

## ANEXĂ Q — SISTEMUL DE NOTĂ ALE OPERATORULUI

### Q.1 Câmpul `notes` al cântării

Fiecare cântare poate avea note interne (câmpul `notes` în tabelul `songs`). Aceste note:
- Sunt vizibile DOAR în fereastra operatorului
- NU se trimit niciodată pe proiector
- Au un fond galben-închis (`#1a1a0a`) și text galben (`#ccaa44`) pentru a fi ușor de distins

### Q.2 Note vs. conținut

Distincția clară:
- **`content`** — textul versurilor, afișat pe proiector
- **`notes`** — instrucțiuni pentru operator (ex. „Cântați de 2 ori", „BPM 120", „Transpozit cu -1")

### Q.3 Note în Stage Monitor

Câmpul `notes` al cântării curente apare și pe monitorul de scenă (`NOTES` widget type), permițând interpreților să vadă instrucțiunile operatorului.

---

## ANEXĂ R — STANDARDUL DE PROCESARE A DATELOR

### R.1 Normalizarea diacriticelor

La salvarea în baza de date, textele cu diacritice românești și maghiare sunt normalizate:
- ă → a, â → a, î → i, ș → s, ț → t (română)
- á → a, é → e, í → i, ó → o, ö → o, ő → o, ú → u, ü → u, ű → u (maghiară)
- Procesul este uni-direcțional: normalizat e doar pentru căutare, originalul rămâne intact

### R.2 Formatul timestamp

Câmpul `created_at` din tabelul `songs` folosește formatul ISO 8601:
`2024-01-15T14:30:00` (fără timezone, ora locală a sistemului)

### R.3 Stocarea setărilor cu tipul corect

Setările sunt stocate ca text în SQLite. La citire, se face conversia:
- `"true"` / `"false"` → boolean (comparare string)
- Numerele → `int()` sau `float()` la citire
- Culorile → string hex `#RRGGBB` sau `#RRGGBBAA`

---

## ANEXĂ S — FLUXURI OPERAȚIONALE TIPICE

### S.1 Fluxul complet — prima utilizare

1. Instalare Cantio → prima pornire
2. Se afișează ecranul splash (900×506 px) cu bara de progres
3. Nu există profiluri → se creează automat profilul „default"
4. Se inițializează baza de date cu schema completă și setările implicite
5. Se pornește tutorialul interactiv (7 pași)
6. Operatorul completează tutorialul → fereastra principală este funcțională

### S.2 Fluxul importului de cântări

1. Operator apasă butonul Import sau Ctrl+I
2. Se deschide file picker (filtru pentru formate suportate)
3. `ImportWorker` (QThread) pornește analiza fișierului
4. Se afișează dialogul `_ImportCategoryDialog` cu numărul de cântări detectate
5. Operatorul alege/confirmă categoria
6. `ImportWorker` importează cântările cu callback de progres (0–100%)
7. Baza de date este actualizată
8. Lista de cântări se reîncarcă (debounce 250 ms)
9. Toast verde „Import complet: X cântări adăugate"
10. Istoricul importului se actualizează în `import_history.json`

### S.3 Fluxul trimiterii live a unui slide

1. Cântarea selectată este încărcată → slide-urile sunt afișate ca miniaturi
2. Operatorul dă click pe o miniatură
3. `SlideThumbnail.clicked` → `control_window._on_slide_clicked(index)`
4. `LiveState.current_text = slide_text`
5. `LiveState.notify()` → toți observatorii sunt notificați
6. `PreviewWidget` rerandează (16 ms delay)
7. `ElectronDisplayProxy.show_text(text, settings)` → WebSocket `show_text`
8. Electron `handleCommand('show_text')` → `broadcast(window_id, msg)`
9. `display.js._handleRender({type:'show_text', text:...})` → animație tranziție + desenare text

### S.4 Fluxul schimbării fundalului la video

1. Operatorul selectează un fișier video din tab-ul Media
2. Apasă „Set as Background" sau trage pe preview
3. `settings['bg_type'] = 'video'`, `settings['bg_video'] = /cale/video.mp4`
4. `ElectronDisplayProxy.apply_settings(settings)` → WebSocket `settings`
5. `display.js` primește `{type:'settings', bg_type:'video', ...}`
6. Se creează un element `<video>` cu `src=` calea video și `loop=true`
7. Video-ul pornește imediat în fundal cu `muted=true` (pentru a permite autoplay)
8. Elementul `<video>` are `z-index:0`, sub ambele canvas-uri

### S.5 Fluxul salvării unui serviciu

1. Operator apasă Ctrl+S sau butonul Salvează
2. Dacă serviciul are deja o cale → se suprascrie direct
3. Dacă nu → se deschide un file picker cu filtru `.gps`
4. `service_manager.save_service()`:
   - Serializează lista de itemi ca `service.json`
   - Creează `metadata.json` cu data curentă și versiunea
   - Împachetează ambele într-un fișier ZIP cu extensia `.gps`
5. Calea noului fișier se adaugă la `recent_services.json` (max 5 intrări)
6. Toast verde „Serviciu salvat"

---

## ANEXĂ T — REZUMAT TIPURI DE MESAJE WEBSOCKET

### T.1 Tabelul complet al comenzilor

| Comandă | Câmpuri obligatorii | Câmpuri opționale | Efect pe ecran |
|---|---|---|---|
| `ping` | — | — | Răspunde cu pong |
| `get_screens` | — | — | Returnează lista de ecrane |
| `open` | `window_id` | `screen_index`, `window_name`, `transparent` | Deschide fereastră |
| `close` | `window_id` | — | Fade-out și închide |
| `quit` | — | — | Oprire Electron (200ms delay) |
| `show_text` | `window_id`, `text` | `title`, `author`, `settings`, `slide_index`, `slide_count` | Afișează versuri |
| `black` | `window_id` | — | Ecran negru |
| `settings` | `window_id` | orice setare de temă | Actualizare setări temă |
| `ticker` | `window_id` | `text`, `speed`, `color`, `bg_color`, `height`, `position` | Pornire ticker |
| `hide_ticker` | `window_id` | — | Ascunde ticker |
| `ticker_advanced` | `window_id` | setări avansate ticker | Ticker cu configurare completă |
| `hide_ticker_effect` | `window_id` | — | Ascunde ticker cu efect de ieșire |
| `timer` | `window_id` | `seconds`, `color` | Pornire countdown |
| `stop_timer` | `window_id` | — | Oprire countdown |
| `clock` | `window_id` | `visible`, `color`, `format`, `position` | Afișare/ascundere ceas |
| `projector_off` | `window_id` | — | Ecran negru total (oprire proiector) |
| `logo` | `window_id` | `path` | Afișare logo |
| `slide_image` | `window_id` | `path` | Afișare imagine pe ecran |
| `show_slide_image` | `window_id` | `path` | Idem (alias) |
| `transparent` | `window_id` | — | Comutare transparent |
| `clear_text` | `window_id` | — | Șterge textul |
| `freeze` | `window_id` | — | Blochează actualizările |
| `unfreeze` | `window_id` | — | Deblochează actualizările |
| `set_transparent` | `window_id` | `screen_index`, `value` | Recreare fereastră transparent |
| `apply_transparent_settings` | `window_id` | orice setare + `bg_transparent` | Setări CSS transparență |

---

## ANEXĂ U — INSTRUCȚIUNI DE RECONSTRUIRE

### U.1 Dependențele Python (requirements)

```
PyQt6>=6.4.0
PyQt6-Qt6>=6.4.0
PyQt6-sip>=13.4.0
PyQt6-Qt6-Multimedia>=6.4.0
websockets>=11.0
flask>=2.3.0
flask-socketio>=5.3.0
python-socketio>=5.8.0
requests>=2.31.0
qrcode[pil]>=7.4.2
opencv-python>=4.8.0 (cv2)
Pillow>=10.0.0
deep-translator>=1.11.0
PyMuPDF>=1.23.0 (fitz)
python-docx>=1.0.0
psutil>=5.9.0
reportlab>=4.0.0
```

### U.2 Dependențele Node.js (display-electron/package.json)

```json
{
  "dependencies": {
    "electron": "^28.0.0",
    "ws": "^8.14.0"
  }
}
```

### U.3 Secvența de instalare

```bash
# 1. Instalare dependențe Python
pip install -r requirements.txt

# 2. Instalare dependențe Node.js
cd display-electron
npm install

# 3. Pornire aplicație
python main.py
```

### U.4 Compilarea pentru distribuție

Cantio poate fi compilat cu PyInstaller pentru a produce `CantioDisplay.exe` (procesul Electron) și `Cantio.exe` (procesul Python). La distribuire, `CantioDisplay.exe` trebuie să fie în același director cu `Cantio.exe`.

---

## ANEXĂ V — CONVENȚII DE COD

### V.1 Denumirile fișierelor de setări

Toate fișierele de configurare JSON sunt în directorul profilului. Convențiile de denumire:
- `settings.json` — setările temei curente (cheie-valoare)
- `playlists.json` — playlist-urile salvate
- `presentations.json` — prezentările grafice
- `stage.json` — layout-ul monitorului de scenă
- `cache.json` — date cache intern (ex. rezultate căutări)

### V.2 Codul de culori

Toate culorile se stochează în format hexazecimal cu prefix `#`:
- `#RRGGBB` pentru culori solide (ex. `#1e1e2e`)
- `#RRGGBBAA` pentru culori cu transparență (ex. `#000000cc`)

Valorile A (alpha) uzuale:
- `cc` = 80% opacitate
- `80` = 50% opacitate
- `40` = 25% opacitate
- `00` = complet transparent

### V.3 Valorile booleane în setări

Setările booleane se stochează ca string-uri:
- `"true"` — adevărat
- `"false"` — fals

Compararea se face întotdeauna ca string: `s.get("font_bold", "true") == "true"`.

### V.4 Coordonatele overlay-urilor

Pozițiile și dimensiunile overlay-urilor din `dual_layout_editor.py` și `overlay_tab.py` sunt întotdeauna în coordonate proporționale (0.0–1.0) față de dimensiunile ecranului. La randare se înmulțesc cu lățimea/înălțimea reală.

---

*Sfârșit document CANTIO_BLUEPRINT.md*
*Versiune: 1.0.0 | Data: 2026 | Autor: Tudor Senegeac*
