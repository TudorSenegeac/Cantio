# Cantio — Funcții și opțiuni complete

> Documentație generată automat din codul sursă al aplicației.  
> Organizare pe categorii. Fiecare funcție include: **Ce face · Fișier · Funcție · Scurtătură (dacă există)**

---

## Cuprins

1. [Afișaj Live (Display)](#1-afișaj-live-display)
2. [Preview & Stare Sincronizată (LiveState)](#2-preview--stare-sincronizată-livestate)
3. [Renderer Partajat](#3-renderer-partajat)
4. [Fereastra Principală de Control](#4-fereastra-principală-de-control)
5. [Biblioteca de Cântări](#5-biblioteca-de-cântări)
6. [Modulul Biblie](#6-modulul-biblie)
7. [Ordinea Serviciului (Service Order)](#7-ordinea-serviciului-service-order)
8. [Controale Live](#8-controale-live)
9. [Ticker / Ceas / Cronometru (Overlay-uri)](#9-ticker--ceas--cronometru-overlay-uri)
10. [Editor Prezentări](#10-editor-prezentări)
11. [Stage Monitor](#11-stage-monitor)
12. [Remote Control Web](#12-remote-control-web)
13. [Import Fișiere](#13-import-fișiere)
14. [Gestionare Profiluri](#14-gestionare-profiluri)
15. [Setări & Configurare](#15-setări--configurare)
16. [Cloud Storage (Supabase)](#16-cloud-storage-supabase)
17. [Scurtături Tastatură](#17-scurtături-tastatură)
18. [Baza de Date & Persistență](#18-baza-de-date--persistență)
19. [Notificări Toast](#19-notificări-toast)
20. [Utilitare Text](#20-utilitare-text)
21. [Traduceri & Limbă interfață](#21-traduceri--limbă-interfață)
22. [Splash Screen & Pornire](#22-splash-screen--pornire)

---

## 1. Afișaj Live (Display)

**Fișier:** `display_window.py`

| Funcție | Ce face | Scurtătură |
|---------|---------|------------|
| `DisplayWindow.__init__` | Creează fereastra de afișaj; stivă de straturi: fundal CSS → `_bg_label` (imagine) → `_video_widget` (video) → `DisplayCanvas` (text/overlay transparent) | — |
| `DisplayCanvas.__init__` | Widget transparent peste fundal; se abonează la `LiveState`; animație de opacitate; redare prin `render_frame(draw_bg=False)` | — |
| `DisplayWindow.apply_settings` | Aplică culoarea fundalului, imaginea de fundal, opacitatea; setează `get_state().bg_pixmap` | — |
| `DisplayWindow.show_text` | Trimite text pe ecran cu animație de fade-in/out; actualizează `LiveState.current_text` | **Space** (GO LIVE) |
| `DisplayWindow.clear_text` | Șterge textul de pe ecran (fade out) | **Escape** |
| `DisplayWindow.set_bg` | Setează imaginea sau video-ul de fundal; pornește redarea video | — |
| `DisplayWindow.freeze_black` | Acoperă tot ecranul cu negru (proiector oprit) | — |
| `DisplayWindow.show_logo` | Afișează imaginea logo configurată; ascunde textul | — |
| `DisplayWindow.set_ticker` | Activează/dezactivează bannerul ticker defilant de la baza ecranului | — |
| `DisplayWindow.set_clock` | Activează/dezactivează ceasul de pe ecran | — |
| `DisplayWindow.set_timer` | Pornește/oprește numărătoarea inversă pe ecran | — |
| `DisplayWindow.toggle_fullscreen` | Comută modul fullscreen al ferestrei de afișaj | **F11** |
| `DisplayWindow.toggle_chroma` | Activează fundalul chroma-key (verde) pentru transmisii live | **Ctrl+Shift+T** |
| `DisplayWindow.closeEvent` | Elimină observatorul din LiveState la închidere | — |

---

## 2. Preview & Stare Sincronizată (LiveState)

**Fișier:** `live_state.py`

| Funcție | Ce face | Scurtătură |
|---------|---------|------------|
| `LiveState.__init__` | Singleton cu toate câmpurile de stare: `current_text`, `opacity`, `settings`, `bg_pixmap`, `bg_video_frame`, `ticker_text/x`, `show_clock`, `timer_remaining`, `logo_mode`, `projector_off` | — |
| `LiveState.add_observer` | Abonează un callback la notificări de stare; apelat de DisplayCanvas și PreviewWidget | — |
| `LiveState.remove_observer` | Dezabonează un callback | — |
| `LiveState.notify` | Notifică toți observatorii (redeclanșează `paintEvent` pe display și preview simultan) | — |
| `LiveState.set_ticker` | Pornește/oprește timer-ul intern (16 ms / 60 fps) pentru animarea ticker-ului; actualizează `ticker_x` | — |
| `LiveState.set_clock` | Pornește/oprește timer-ul de ceas (500 ms) | — |
| `LiveState.set_timer` | Pornește/oprește numărătoarea inversă (1 s) | — |
| `LiveState.stop_all_timers` | Oprește toate timer-urile interne; apelat la resetare profil | — |
| `get_state()` | Returnează instanța singleton globală `LiveState` | — |
| `reset_state()` | Oprește timer-urile și creează un nou `LiveState` curat | — |

**Fișier:** `preview_widget.py`

| Funcție | Ce face | Scurtătură |
|---------|---------|------------|
| `PreviewWidget.__init__` | Se abonează la `LiveState`; redă frame-uri cu `render_frame(draw_bg=True)` | — |
| `PreviewWidget.apply_settings` | Scrie setările în `LiveState`; încarcă `bg_pixmap` din cale | — |
| `PreviewWidget.update_text` | Actualizează `LiveState.current_text` | — |
| `PreviewWidget.paintEvent` | Redă frame-ul complet + indicator **● LIVE** (verde) sau **◎ PREVIEW** (gri) | — |

---

## 3. Renderer Partajat

**Fișier:** `renderer.py`

| Funcție | Ce face |
|---------|---------|
| `render_frame(painter, state, w, h, scale, draw_bg)` | Funcție centrală de randare folosită atât de DisplayCanvas cât și de PreviewWidget; `draw_bg=True` randează și fundalul (preview), `draw_bg=False` îl omite (display transparent) |
| `_draw_lyrics` | Randează textul cu auto-scalare font, umbre, aliniere H/V configurabilă, opacitate, word-wrap |
| `_draw_overlays` | Randează ticker defilant, ceas digital, cronometru cu modificare de culoare când < 30 s |
| `_draw_bg_pixmap` | Centrează și cropează imaginea de fundal prin `KeepAspectRatioByExpanding` |

**Fișier:** `text_utils.py`

| Funcție | Ce face |
|---------|---------|
| `wrap_text_to_fit(text, font_family, font_size, ...)` | Word-wrap cu micșorare automată a fontului până când textul încape în dreptunghiul disponibil |
| `apply_sacred_caps(text, words, allcaps)` | Substituie cuvintele sacre (ex. "isus" → "Isus") sau le pune cu MAJUSCULE |
| `_wrap_line(line, fm, max_width)` | Word-wrap pe o singură linie bazat pe lățimea pixelilor |

---

## 4. Fereastra Principală de Control

**Fișier:** `control_window.py`

| Funcție | Ce face | Scurtătură |
|---------|---------|------------|
| `ControlWindow.__init__` | Inițializează fereastra principală; deschide display-urile; pornește remote server; inițializează toast, stage monitor, scurtături | — |
| `ControlWindow._build_toolbar` | Construiește bara de instrumente cu butoane Import, Cântec Nou, Salvare Serviciu, Setări, Scurtături, Stage Monitor | — |
| `ControlWindow._build_songs_tab` | Tab „Cântări": căutare, filtru categorie, listă cântări, thumbnails slide-uri, editor cântec | — |
| `ControlWindow._build_bible_tab` | Tab „Biblie": selector carte/capitol/verset, previzualizare text, buton Trimite Live | — |
| `ControlWindow._build_slides_tab` | Tab „Slide-uri": lista prezentărilor create, thumbnails; deschide editorul de prezentări | — |
| `ControlWindow._search_songs` | Caută în baza de date după titlu sau conținut cu filtru de categorie | **Ctrl+F** |
| `ControlWindow._load_song` | Încarcă cântecul selectat; populează panoul de slide-uri cu thumbnails | — |
| `ControlWindow._send_slide` | Trimite slide-ul selectat pe display + actualizează stage monitor | **→ / ↓** (slide următor) / **← / ↑** (slide anterior) |
| `ControlWindow._go_live` | Trimite slide-ul curent pe toate display-urile active | **Space** |
| `ControlWindow._toggle_freeze` | Comută ecranul negru (proiector oprit/pornit) | **Escape** |
| `ControlWindow._show_logo` | Afișează logo-ul pe toate display-urile | — |
| `ControlWindow._new_song` | Deschide dialogul de creare cântec nou | — |
| `ControlWindow._edit_song` | Deschide editorul pentru cântecul selectat | — |
| `ControlWindow._delete_song` | Șterge cântecul din baza de date cu confirmare | — |
| `ControlWindow._add_to_service` | Adaugă cântecul selectat la ordinea serviciului | — |
| `ControlWindow._save_service` | Salvează serviciul curent ca fișier `.gps` | **Ctrl+S** |
| `ControlWindow._load_service` | Deschide un fișier `.gps` și populează lista serviciului | **Ctrl+O** |
| `ControlWindow._new_service` | Curăță lista serviciului (cu confirmare dacă e nesalvat) | **Ctrl+N** |
| `ControlWindow._open_import_manager` | Deschide ImportManager pentru import fișiere | **Ctrl+I** |
| `ControlWindow._open_settings` | Deschide dialogul de setări | — |
| `ControlWindow._open_shortcuts` | Deschide dialogul cu toate scurtăturile de tastatură | — |
| `ControlWindow._toggle_stage_monitor` | Deschide/ascunde fereastra Stage Monitor Editor | **Ctrl+Shift+P** |
| `ControlWindow._toggle_display` | Arată/ascunde fereastra de afișaj live | **Ctrl+P** |
| `ControlWindow._update_send_combo` | Actualizează combo-box-ul de selectare display (All / individual) | — |
| `ControlWindow._mark_service_modified` | Marchează serviciul ca nesalvat în bara de titlu | — |
| `ControlWindow._select_pres_slide` | Trimite slide-ul de prezentare selectat pe display și preview | — |
| `ControlWindow.keyPressEvent` | Interceptează tastele de navigare globale (arrows, space, escape) când focusul nu e într-un text edit | — |
| `SongEditorDialog` | Dialog modal pentru creare/editare cântec: titlu, autor, categorie, limbă, text cu slide-uri, note operator | — |
| `SmartTextEdit` | QTextEdit extins care trimite Ctrl+Enter ca semnal `send_requested` | — |

---

## 5. Biblioteca de Cântări

**Fișier:** `database.py`

| Funcție | Ce face |
|---------|---------|
| `add_song(title, content, slides, author, category, language, notes)` | Adaugă cântec nou în `songs.db`; returnează `song_id` |
| `update_song(song_id, ...)` | Actualizează toate câmpurile unui cântec existent |
| `delete_song(song_id)` | Șterge cântecul și îl elimină și din playlist |
| `get_all_songs(category)` | Returnează toate cântecele, opțional filtrate după categorie |
| `search_songs(query, category)` | Caută în titlu și conținut (LIKE) cu filtru categorie opțional |
| `get_song(song_id)` | Returnează un cântec după ID cu slide-uri parsate din JSON |
| `get_categories()` | Returnează lista categoriilor unice + categoriile built-in |

**Categorii built-in:** All, General, Imnuri, Psalmi, Colinde, Laude, Rugăciuni, Recunoștință, Evanghelie, Copii

---

## 6. Modulul Biblie

**Fișier:** `database.py`

| Funcție | Ce face |
|---------|---------|
| `get_bible_books()` | Returnează toate cărțile biblice ordonate |
| `get_chapters(book_id)` | Returnează lista capitolelor dintr-o carte |
| `get_verses(book_id, chapter)` | Returnează versetele unui capitol |
| `get_verse(book_id, chapter, verse_num)` | Returnează un verset specific |
| `search_bible_text(query, limit)` | Caută în textul versetelor (full-text LIKE, max 80 rezultate) |
| `import_bible_data(books, verses)` | Importă o traducere biblică completă (șterge și reimportă) |
| `has_bible()` | Returnează `True` dacă există o traducere importată |

---

## 7. Ordinea Serviciului (Service Order)

**Fișier:** `service_manager.py`

| Funcție | Ce face |
|---------|---------|
| `save_service(path, items, profile_name)` | Salvează serviciul ca fișier `.gps` (arhivă ZIP cu `service.json` + `metadata.json`) |
| `load_service(path)` | Încarcă un fișier `.gps`; returnează `{"items": [...], "metadata": {...}}` |
| `get_recent_files()` | Returnează ultimele 5 fișiere `.gps` deschise |
| `add_recent_file(path)` | Adaugă calea la lista de fișiere recente |
| `remove_recent_file(path)` | Elimină o cale din lista recentă |
| `register_file_association(exe_path)` | Înregistrează extensia `.gps` în Registrul Windows pentru dublu-clic |
| `unregister_file_association()` | Elimină înregistrarea `.gps` din Registry |

**Fișier:** `database.py`

| Funcție | Ce face |
|---------|---------|
| `get_playlist()` | Returnează playlist-ul curent (items cu song_id, titlu, slide-uri, note) |
| `add_to_playlist(song_id, label)` | Adaugă cântecul în playlist la final |
| `remove_from_playlist(playlist_id)` | Elimină un item din playlist |
| `clear_playlist()` | Curăță întregul playlist |
| `reorder_playlist(ordered_ids)` | Reordonează itemii din playlist |
| `save_playlists(items)` | Suprascrie complet playlist-ul |

---

## 8. Controale Live

**Fișier:** `control_window.py`

| Funcție | Ce face | Scurtătură |
|---------|---------|------------|
| `_go_live` | Trimite slide-ul curent pe display cu fade-in | **Space** |
| `_toggle_freeze` | Ecran negru / revenire la slide curent | **Escape** |
| `_show_logo` | Afișează imaginea logo configurată | — |
| `_next_slide` | Avansează la slide-ul următor și trimite live | **→** sau **↓** |
| `_prev_slide` | Revine la slide-ul anterior și trimite live | **←** sau **↑** |
| `_send_to_display` | Trimite slide-ul pe display-ul selectat (All / specific) | — |

---

## 9. Ticker / Ceas / Cronometru (Overlay-uri)

**Fișier:** `control_window.py` + `live_state.py` + `renderer.py`

| Funcție | Ce face |
|---------|---------|
| `LiveState.set_ticker(text, enabled)` | Activează ticker-ul defilant cu textul dat; timer intern 16 ms actualizează `ticker_x` |
| `LiveState.set_clock(enabled)` | Activează/dezactivează ceasul digital pe display |
| `LiveState.set_timer(seconds, enabled)` | Pornește numărătoarea inversă; culoarea devine roșie sub 30 s |
| `_draw_overlays` (renderer.py) | Randează ticker, ceas (`datetime.now().strftime`), cronometru cu aceeași logică pe display și preview |
| Ticker alert (control_window) | Câmp text + buton „Trimite" pentru a seta mesajul ticker în timp real |
| Countdown controls (control_window) | Câmpuri minute:secunde + Start/Stop/Reset pentru numărătoarea inversă |

---

## 10. Editor Prezentări

**Fișier:** `presentation_editor.py`

| Funcție | Ce face |
|---------|---------|
| `PresentationEditorWindow.__init__` | Fereastra principală a editorului: panou slide-uri (stânga), canvas editabil (centru), panou proprietăți (dreapta) |
| `render_slide_to_pixmap(slide_data, w, h)` | Randează un slide la un QPixmap de dimensiunea dată; folosit pentru thumbnails |
| `SlideCanvas` | Widget canvas cu drag & drop pentru elemente text, imagine, dreptunghi, elipsă |
| `SlideCanvas.paintEvent` | Randează toate elementele slide-ului curent, cu handles de selecție/resize |
| `SlideCanvas.mousePressEvent` | Click: selectează elementul sub cursor sau deselectează |
| `SlideCanvas.mouseMoveEvent` | Drag: mută sau redimensionează elementul selectat (colțuri) |
| `ElementPropertiesPanel` | Panou dreapta: editare proprietăți element (font, culoare, aliniere, imagine, gradient) |
| `_add_text_element` | Adaugă un element text pe slide cu poziție și dimensiune implicite |
| `_add_image_element` | Adaugă un element imagine; deschide file picker |
| `_add_rect_element` | Adaugă un dreptunghi cu culoare de fundal și border configurabile |
| `_add_ellipse_element` | Adaugă o elipsă/cerc |
| `_save_presentation` | Salvează prezentarea în `presentations.json` via `db.update_presentation` |
| `_new_slide` | Adaugă un slide nou la prezentare |
| `_duplicate_slide` | Duplică slide-ul curent |
| `_delete_slide` | Șterge slide-ul curent (cu confirmare) |
| `_reorder_slides` | Mută slide-ul în sus/jos în listă |
| `_export_slides_png` | Exportă fiecare slide ca fișier PNG |

**Tipuri de elemente suportate:** `text`, `image`, `rect`, `ellipse`

---

## 11. Stage Monitor

**Fișier:** `stage_monitor.py`

| Funcție | Ce face | Scurtătură |
|---------|---------|------------|
| `StageEditorWindow.__init__` | Editor vizual drag & drop pentru layout-ul monitorului de scenă; deschis din toolbar | **Ctrl+Shift+P** |
| `StageCanvas` | Canvas editabil: click = selectare widget, drag = mutare, colțuri = redimensionare |
| `StageCanvas.paintEvent` | Randează toate widget-urile cu fundalul de grilă și outline; indicator de selecție albastru |
| `render_stage_widget` | Funcție de randare partajată (canvas editor + output fullscreen) pentru un widget de scenă |
| `get_widget_display_text` | Returnează textul de afișat pentru fiecare tip: slide curent, următor, ceas, cronometru, note, text custom |
| `WidgetPropertiesPanel` | Panou dreapta: font, culori, aliniere, text custom, cale imagine, vizibilitate, prefix tip |
| `_add_widget(wtype)` | Adaugă un widget nou pe canvas (cu poziție implicită tip-specifică) |
| `_save_layout` | Salvează layout-ul în `settings.json` via `db.save_setting("stage_layout", ...)` |
| `_load_layout` | Încarcă layout-ul salvat la pornire |
| `_load_layout_file` | Importă layout dintr-un fișier JSON extern |
| `_clear_all` | Șterge toate widget-urile (cu confirmare) |
| `_open_output` | Deschide `StageOutputWindow` fullscreen pe ecranul selectat | — |
| `_close_output` | Închide fereastra de output fullscreen | — |
| `StageOutputWindow` | Fereastră fullscreen fără ramă, stays on top; actualizează textul curent/următor/note în timp real |
| `StageEditorWindow.update_state` | Apelat de `ControlWindow` la fiecare schimbare de slide; actualizează canvas + output simultan |

**Tipuri de widget-uri:** `CURRENT_SLIDE`, `NEXT_SLIDE`, `CLOCK`, `TIMER`, `NOTES`, `CUSTOM_TEXT`, `IMAGE`

---

## 12. Remote Control Web

**Fișier:** `remote_server.py`

| Funcție | Ce face |
|---------|---------|
| `start_server(port)` | Pornește serverul Flask într-un thread daemon pe portul 5050 (implicit) |
| `stop_server()` | Setează flag-ul `_running = False`; thread-ul daemon se oprește cu aplicația |
| `is_running()` | Returnează `True` dacă serverul rulează |
| `update_state(**kwargs)` | Apelat din thread-ul Qt pentru a actualiza starea partajată citită de Flask |
| `get_url()` | Returnează URL-ul de acces local (ex. `http://192.168.1.10:5050`) |
| `get_local_ip()` | Detectează IP-ul local real prin socket UDP |
| `pop_command()` | Extrage o comandă din coada thread-safe; apelat periodic de Qt via QTimer |
| `GET /` | Servește interfața HTML mobile-first dark-mode |
| `GET /api/state` | Returnează starea curentă ca JSON (text live, titlu, index slide, is_live, ticker, countdown etc.) |
| `POST /api/command` | Primește comenzi de la interfața web și le pune în coada de comenzi |

**Comenzi suportate din browser:**
`go_live`, `black`, `freeze`, `logo`, `prev`, `next`, `ticker`, `countdown_start`, `countdown_stop`, `service_select`, `load_song`

---

## 13. Import Fișiere

**Fișier:** `importer.py`

| Funcție | Ce face |
|---------|---------|
| `import_file(filepath)` | Dispatcher universal: detectează formatul după extensie și apelează importerul corespunzător |
| `import_txt(filepath)` | Importă fișier `.txt`; detecție automată encoding; split pe paragrafe goale → slide-uri |
| `import_docx(filepath)` | Importă `.docx` via `python-docx`; paragrafele → slide-uri |
| `import_pdf(filepath)` | Importă `.pdf` via `PyMuPDF (fitz)`; fiecare pagină → slide |
| `import_videopasalm_json(filepath)` | Importă colecție de cântece din VideoPsalm `.json` |
| `import_videopasalm_xml(filepath)` | Importă din VideoPsalm `.xml` cu suport structuri multiple (`<song>`, `<verse>`, `<strophe>`) |
| `import_vpc(filepath)` | Importă arhivă `.vpc` (ZIP cu fișiere `.song` XML); fallback la XML/JSON simplu |
| `import_easyworship_ewsx(filepath)` | Importă `.ewsx` (ZIP cu XML/JSON); fallback automat la SQLite |
| `import_easyworship_db(filepath)` | Importă baza SQLite EasyWorship 6; suport coloane RTF și multiple scheme |
| `import_easyworship7_db(filepath)` | Importă `song.db` EasyWorship 7 cu lirice în format JSON |
| `detect_easyworship7_default_path()` | Detectează automat calea default a bazei EW7 pe mașina curentă |
| `import_bib(filepath)` | Importă traducere biblică `.bib`; încearcă XML → SQLite → text simplu |
| `detect_encoding(filepath)` | Detectează encoding-ul unui fișier (BOM sniffing + trial UTF-8/CP1250/ISO-8859-2 etc.) |
| `strip_rtf(text)` | Extrage text simplu din string RTF (font table, colortbl, `\uN`, `\'xx`, `\par`) |
| `text_to_slides(text)` | Split text pe paragrafe duble → listă de slide-uri |

**Formate suportate:** `.txt`, `.docx`, `.pdf`, `.json`, `.xml`, `.vpc`, `.ewsx`, `.db` (EW6/EW7), `.bib`

**Fișier:** `import_manager.py`

| Funcție | Ce face |
|---------|---------|
| `ImportManager.__init__` | Fereastră de import cu log în timp real, progress bar, buton Browse multiplu |
| `_browse_files` | Deschide file picker; suportă selecție multiplă |
| `_run_import` | Rulează importul în thread background; raportează progres și erori în log |
| `_on_import_done` | Actualizează lista de cântări și afișează toast de succes/eroare |

---

## 14. Gestionare Profiluri

**Fișier:** `profile_manager.py`

| Funcție | Ce face |
|---------|---------|
| `list_profiles()` | Returnează lista de profiluri din `~/Cantio/profiles/` |
| `create_profile(name)` | Creează directorul profilului |
| `delete_profile(name)` | Șterge recursiv directorul profilului |
| `rename_profile(old_name, new_name)` | Redenumește directorul profilului |
| `get_last_profile()` | Citește ultimul profil folosit din `last_profile.json` |
| `save_last_profile(name)` | Salvează numele profilului curent |
| `has_legacy_db()` | Verifică dacă există baza de date monolitică veche |
| `migrate_legacy_to_profile(profile_name)` | Copiază `cantio.db` vechi în directorul noului profil |
| `ProfileSelectDialog` | Dialog de selecție profil la pornire: listă profiluri, buton Nou/Redenumire/Ștergere, Open; ultimul profil marcat cu ★ |
| `ProfileSelectDialog._check_migration` | Detectează baza veche și propune migrarea automată la primul profil |
| `ProfileSelectDialog.exec` | Dacă nu se selectează nimic, folosește ultimul profil sau creează `Default` |

---

## 15. Setări & Configurare

**Fișier:** `settings_dialog.py`

| Funcție | Ce face |
|---------|---------|
| `SettingsDialog.__init__` | Dialog cu tab-uri pentru toate setările aplicației |
| `_tab_display` | **Tab Afișaj:** ecran target, rezoluție, culoare fundal, imagine fundal, opacitate |
| `_tab_typography` | **Tab Tipografie:** familie font, dimensiune, bold/italic, culoare text, umbră, outline, spațiere rânduri, margine, aliniere H/V |
| `_tab_video` | **Tab Video:** cale video fundal, opacitate video |
| `_tab_ticker` | **Tab Ticker:** text, viteză, culoare text, culoare fundal |
| `_tab_clock` | **Tab Ceas:** activare/dezactivare, culoare, format (HH:MM:SS / HH:MM) |
| `_tab_countdown` | **Tab Cronometru:** activare, secunde inițiale, culoare |
| `_tab_advanced` | **Tab Avansat:** cuvinte sacre (enable/allcaps/listă), auto-advance, logo path, Supabase URL/key/bucket, dimensiune thumbnail |
| `_tab_interface` | **Tab Interfață:** dropdown limbă (Română/English/Deutsch/Français/Magyar), notă „restart necesar" |
| `_tab_per_window` | **Tab Ferestre:** configurații per-display (ecran, fullscreen, override setări locale) |
| `_load_values` | Populează toate câmpurile cu valorile din `db.get_settings()` |
| `_collect` | Colectează valorile din toate câmpurile într-un dict |
| `_accept` | Salvează setările, detectează schimbarea limbii, afișează mesaj restart |
| `WindowPerSettingsDialog` | Sub-dialog pentru configurarea unui display individual |

**Setări disponibile (chei):**

| Cheie | Descriere | Implicit |
|-------|-----------|---------|
| `display_screen` | Indexul ecranului pentru display | `"1"` |
| `stage_screen` | Ecran Stage Monitor | `"2"` |
| `bg_color` | Culoare fundal display | `"#000000"` |
| `text_color` | Culoare text | `"#ffffff"` |
| `font_family` | Familie font | `"Arial"` |
| `font_size` | Dimensiune font (pt) | `"48"` |
| `font_bold` | Text bold | `"true"` |
| `font_italic` | Text italic | `"false"` |
| `text_shadow` | Umbră text | `"true"` |
| `line_spacing` | Spațiere rânduri (multiplicator) | `"1.4"` |
| `margin` | Margine (px) | `"60"` |
| `outline_color` | Culoare contur text | `"#000000"` |
| `outline_width` | Grosime contur (px) | `"2"` |
| `bg_image` | Cale imagine fundal | `""` |
| `bg_opacity` | Opacitate imagine fundal | `"0.5"` |
| `bg_video` | Cale video fundal | `""` |
| `bg_video_opacity` | Opacitate video | `"1.0"` |
| `ticker_text` | Text ticker defilant | `""` |
| `ticker_enabled` | Activare ticker | `"false"` |
| `ticker_speed` | Viteză ticker (px/frame) | `"2"` |
| `ticker_color` | Culoare text ticker | `"#ffffff"` |
| `ticker_bg` | Culoare fundal ticker (cu alpha) | `"#000000cc"` |
| `clock_enabled` | Activare ceas pe display | `"false"` |
| `clock_color` | Culoare ceas | `"#ffffff"` |
| `clock_format` | Format ceas | `"HH:MM:SS"` |
| `countdown_enabled` | Activare cronometru | `"false"` |
| `countdown_seconds` | Secunde inițiale cronometru | `"300"` |
| `countdown_color` | Culoare cronometru | `"#ffffff"` |
| `text_align` | Aliniere orizontală text | `"center"` |
| `text_valign` | Aliniere verticală text | `"center"` |
| `auto_advance` | Avansare automată slide-uri | `"false"` |
| `auto_advance_seconds` | Interval avansare auto (s) | `"5"` |
| `sacred_words_enabled` | Capitalizare automată cuvinte sacre | `"false"` |
| `sacred_words_allcaps` | Cuvinte sacre cu MAJUSCULE | `"false"` |
| `sacred_words` | Lista cuvintelor sacre (CSV) | `"Jesus,Isus,..."` |
| `supabase_url` | URL proiect Supabase | `""` |
| `supabase_key` | API key Supabase | `""` |
| `supabase_bucket` | Bucket Supabase | `"cantio-media"` |
| `stage_layout` | Layout Stage Monitor (JSON) | `"[]"` |
| `thumb_size` | Dimensiune thumbnails slide-uri (S/M/L) | `"S"` |
| `language` | Limba interfeței | `"ro"` |
| `display_configs` | Configurații ferestre display (JSON array) | default 1 proiector |

---

## 16. Cloud Storage (Supabase)

**Fișier:** `cloud_manager.py`

| Funcție | Ce face |
|---------|---------|
| `upload_file(url, key, bucket, local_path, progress_cb)` | Uploadează un fișier media în bucket-ul Supabase; upsert automat dacă fișierul există deja; progress callback |
| `list_files(url, key, bucket)` | Listează fișierele din bucket (max 500) |
| `download_file(url, key, bucket, filename, progress_cb)` | Descarcă fișier în cache local (`~/Cantio/cache/cloud/`); skip dacă e deja în cache |
| `delete_file(url, key, bucket, filename)` | Șterge un fișier din bucket |
| `get_public_url(url, bucket, filename)` | Generează URL-ul public al unui fișier |
| `test_connection(url, key, bucket)` | Testează conexiunea la Supabase; returnează `(ok, message)` |
| `is_image(filename)` | Verifică dacă fișierul este imagine (jpg, png, webp, gif, bmp) |
| `is_video(filename)` | Verifică dacă fișierul este video (mp4, mov, avi, mkv, webm) |

**Nota:** Necesită biblioteca `requests`. Nu necesită `supabase-py`.

---

## 17. Scurtături Tastatură

**Fișier:** `keyboard_shortcuts.py`

| Grup | Acțiune | Scurtătură |
|------|---------|------------|
| Navigare slide-uri | Slide următor + trimite live | **→** / **↓** |
| Navigare slide-uri | Slide anterior + trimite live | **←** / **↑** |
| Navigare slide-uri | GO LIVE (slide curent) | **Space** |
| Navigare slide-uri | Black Screen (ecran negru) | **Escape** |
| Ferestre | Toggle fereastră live (display) | **Ctrl+P** |
| Ferestre | Toggle Stage Monitor | **Ctrl+Shift+P** |
| Ferestre | Toggle Transparent / Chroma-key | **Ctrl+Shift+T** |
| Ferestre | Fullscreen display (toggle) | **F11** |
| Serviciu | Salvează serviciu curent | **Ctrl+S** |
| Serviciu | Deschide serviciu (.gps) | **Ctrl+O** |
| Serviciu | Serviciu nou (șterge lista) | **Ctrl+N** |
| Aplicație | Focus căutare cântări | **Ctrl+F** |
| Aplicație | Deschide Import Manager | **Ctrl+I** |

`ShortcutsDialog` — Dialog tabel cu toate scurtăturile, grupate pe categorii cu culori distincte.

> **Notă:** Scurtăturile de navigare funcționează când cursorul nu este în câmp text.

---

## 18. Baza de Date & Persistență

**Fișier:** `database.py`

### Structura de fișiere per profil

```
~/Cantio/profiles/<Nume>/
├── songs.db          # SQLite — cântări
├── bible.db          # SQLite — cărți și versete biblice
├── settings.json     # JSON  — setările aplicației
├── playlists.json    # JSON  — playlist / serviciu curent
├── presentations.json# JSON  — prezentări custom
├── stage.json        # JSON  — layout-uri Stage Monitor
└── cache.json        # JSON  — fișiere recente, stare UI
```

| Funcție | Ce face |
|---------|---------|
| `set_active_profile(name)` | Setează toate căile de fișiere pentru profilul activ |
| `get_active_profile()` | Returnează numele profilului activ |
| `init_db()` | Creează tabelele SQLite și fișierele JSON dacă nu există; rulează migrarea din format vechi |
| `_migrate_from_monolithic()` | Migrează automat din `cantio.db` monolitic la structura split; redenumește fișierul vechi la `.migrated` |
| `get_settings()` | Citește `settings.json` cu fallback la defaults |
| `save_setting(key, value)` | Salvează o singură setare |
| `save_settings(settings_dict)` | Salvează un dict de setări |
| `get_display_configs()` | Returnează configurațiile ferestrelor de display |
| `save_display_configs(configs)` | Salvează configurațiile display-urilor |
| `get_window_state()` / `save_window_state(state)` | Persistă starea UI (splitter, tab activ) în `cache.json` |
| `get_cache()` / `save_cache(data)` | Acces direct la `cache.json` |
| `get_recent_files()` / `add_recent_file(path)` | Gestionează lista ultimelor 20 fișiere deschise |
| `get_stage_layouts()` / `save_stage_layout(name, data)` | Stochează/citește layout-urile Stage Monitor în `stage.json` |
| `add_presentation` / `update_presentation` / `delete_presentation` / `get_all_presentations` / `get_presentation` | CRUD complet pentru prezentări în `presentations.json` |
| `export_db_json(path)` | Exportă cântecele + biblia + prezentările într-un singur fișier JSON |

---

## 19. Notificări Toast

**Fișier:** `toast_notifications.py`

| Funcție | Ce face |
|---------|---------|
| `ToastManager.__init__(parent)` | Atașat la QMainWindow; gestionează stiva de notificări |
| `ToastManager.info(message)` | Afișează notificare albastră (info) |
| `ToastManager.warning(message)` | Afișează notificare galbenă (avertisment) |
| `ToastManager.error(message)` | Afișează notificare roșie (eroare) |
| `ToastManager.success(message)` | Afișează notificare verde (succes) |
| `ToastManager.show(message, kind)` | Afișează un toast; max 3 simultane, cel mai vechi se elimină dacă limita e depășită |
| `ToastWidget` | Widget individual: slide-in din dreapta, auto-dismiss după 4 s, click pentru închidere imediată, fade-out la dispariție |
| `ToastManager._reposition` | Repoziționează stiva de toasturi bottom-right în fereastra principală |

**Tipuri:** `info` (albastru) · `warning` (galben) · `error` (roșu) · `success` (verde)

---

## 20. Utilitare Text

**Fișier:** `text_utils.py`

| Funcție | Ce face |
|---------|---------|
| `wrap_text_to_fit(text, font_family, font_size, font_bold, font_italic, line_spacing, max_width, max_height, min_font_size)` | Word-wrap cu scalare automată a fontului (descendent de la `font_size` până la `min_font_size`) până când textul încape complet în dreptunghiul dat |
| `apply_sacred_caps(text, words, allcaps)` | Substituie cuvintele sacre cu forma canonică (capitalizate) sau MAJUSCULE |
| `_wrap_line(line, fm, max_width)` | Auxiliar: word-wrap pe o singură linie bazat pe `QFontMetrics.horizontalAdvance` |

**Cuvinte sacre implicite:** Jesus, Isus, Iisus, God, Dumnezeu, Hristos, Christ, Domnul, Holy Spirit, Duhul Sfânt, Emanuel, Tatăl, Fiul, Mesia, Aleluia, Amin

---

## 21. Traduceri & Limbă interfață

**Fișier:** `translations.py`

| Funcție | Ce face |
|---------|---------|
| `t(key)` | Returnează string-ul tradus pentru cheia dată în limba curentă; fallback la română dacă cheia lipsește |
| `set_language(lang)` | Setează limba curentă (cod ISO 639-1: `ro`, `en`, `de`, `fr`, `hu`) |
| `get_language()` | Returnează codul limbii curente |
| `available_languages()` | Returnează dict `{cod: nume_afișat}` pentru toate cele 5 limbi |

**Limbi suportate:** Română (`ro`) · English (`en`) · Deutsch (`de`) · Français (`fr`) · Magyar (`hu`)

**~60+ chei traduse**, inclusiv: toate butoanele, label-urile, mesajele de confirmare, statusurile de splash screen, mesajele de eroare.

Limba este salvată în `settings.json["language"]` și aplicată:
1. La pornire — înainte de crearea oricărui widget (citit din profilul Default)
2. După selecția profilului — re-aplicat cu setările profilului ales

---

## 22. Splash Screen & Pornire

**Fișier:** `splash_screen.py`

| Funcție | Ce face |
|---------|---------|
| `run_splash(callback)` | Afișează splash screen animat și apelează `callback(splash)` după animație |
| `SplashScreen.set_status(text, percent)` | Actualizează textul de status și bara de progres în timp real |
| `SplashScreen.finish` | Închide splash-ul cu fade-out |

**Fișier:** `main.py`

| Funcție | Ce face |
|---------|---------|
| `main()` | Punctul de intrare: creează `QApplication`, setează `quitOnLastWindowClosed=False`, citește limba, pornește splash, deschide dialog profil, inițializează DB, lansează `ControlWindow` |
| `_launch(splash)` | Callback apelat din splash: selectare profil → `init_db()` → `ControlWindow` → `window.destroyed.connect(app.quit)` |
| `_ensure_splash_closed()` | Safety net la 2800 ms: forțează închiderea splash-ului și aduce dialogul de profil în față |
| `_set_app_icon(app)` | Setează iconița aplicației din `Cantio_icon.png` |

---

## Arhitectura generală

```
main.py
  └── ControlWindow (control_window.py)
        ├── LiveState (live_state.py)          ← stare centralizată
        │     ├── DisplayWindow (display_window.py)
        │     │     └── DisplayCanvas          ← render transparent
        │     └── PreviewWidget (preview_widget.py)  ← render complet
        ├── renderer.py                        ← render partajat
        ├── StageEditorWindow (stage_monitor.py)
        ├── ImportManager (import_manager.py)
        │     └── importer.py                 ← parsere formate
        ├── SettingsDialog (settings_dialog.py)
        ├── ToastManager (toast_notifications.py)
        ├── remote_server.py                   ← Flask daemon thread
        └── database.py                        ← persistență
              ├── songs.db (SQLite)
              ├── bible.db (SQLite)
              ├── settings.json
              ├── playlists.json
              ├── presentations.json
              ├── stage.json
              └── cache.json
```

---

*Ultima actualizare: 2026-04-28*
