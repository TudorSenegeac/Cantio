"""
Cantio - Online Songs Tab
Primary: cantaricrestine.ro API; fallback: resursecrestine.ro scraping.
"""
from __future__ import annotations

import os
import re
import json
import time
import random
import logging
import urllib.parse

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QTextEdit,
    QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

API_BASE = "https://www.cantaricrestine.ro/api.php"
BASE_URL = "https://www.resursecrestine.ro"
RC_BASE  = BASE_URL

_log = logging.getLogger("Cantio.online")

# ── Online song cache ─────────────────────────────────────────────────────────

from paths import get_data_dir as _get_data_dir
CACHE_FILE = os.path.join(_get_data_dir(), "online_cache.json")
CACHE_EXPIRY_HOURS = 24


def load_online_cache() -> dict:
    try:
        if not os.path.exists(CACHE_FILE):
            return {}
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_online_cache(cache: dict):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _log.error("Cache save error: %s", e)


def get_cached_song(url: str) -> "dict | None":
    """Return cached song data if present and not expired (24 h)."""
    cache = load_online_cache()
    entry = cache.get(url)
    if not entry:
        return None
    age_hours = (time.time() - entry.get("timestamp", 0)) / 3600
    if age_hours > CACHE_EXPIRY_HOURS:
        return None
    return entry.get("data")


def cache_song(url: str, data: dict):
    """Persist song data keyed by URL; keep cache ≤ 100 entries."""
    cache = load_online_cache()
    cache[url] = {"timestamp": time.time(), "data": data}
    if len(cache) > 100:
        oldest = sorted(cache.items(), key=lambda x: x[1].get("timestamp", 0))
        for old_url, _ in oldest[:20]:
            del cache[old_url]
    save_online_cache(cache)


def clear_online_cache():
    """Delete all cached entries."""
    try:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
    except Exception as e:
        _log.error("Cache clear error: %s", e)


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ro-RO,ro;q=0.9",
    "Referer": BASE_URL,
}

# Navigation phrases that appear in page text but aren't lyrics
_NAV_PHRASES = [
    "pentru mai multe", "vizitati pagina", "autentifica", "adauga comentar",
    "statistici", "vizualizari", "proiecteaza", "de acelasi autor",
    "din acelasi album", "pasajul zilei", "un gand", "pune-l pe",
    "radio crestin", "index alfabetic", "ultimele adaugate", "inapoi", "inainte",
    "copyright", "toate drepturile", "resurse crestine",
]

# Markers that start a new stanza/section
_STANZA_MARKERS = re.compile(
    r"^(\d+\.|R:|Ref:|C:|Bridge:|Pod:|Cor:|Intro:|Outro:|"
    r"Pre-refren:|Strofa|STROFA|REFREN|Chorus)",
    re.IGNORECASE,
)


# ── Search Thread ─────────────────────────────────────────────────────────────

class SearchThread(QThread):
    results_ready = pyqtSignal(list)
    error         = pyqtSignal(str)

    def __init__(self, query: str):
        super().__init__()
        self.query = query

    # ── Main entry: try API first, then RC scraping ───────────────────────────
    def run(self):
        try:
            import requests
        except ImportError as e:
            self.error.emit(f"Lipsesc pachete: {e}\nInstalează: pip install requests beautifulsoup4")
            return

        # ── 1. Încearcă API cantaricrestine.ro ───────────────────────────────
        try:
            token  = random.randint(100_000, 999_999)
            params = urllib.parse.urlencode({
                "token":  str(token),
                "cauta":  self.query,
                "limita": "25",
            })
            url = f"{API_BASE}?{params}"
            print(f"[ONLINE] API: {url}")

            r = requests.get(
                url,
                headers={"User-Agent": "Cantio/1.0", "Accept": "application/json"},
                timeout=15,
            )
            print(f"[ONLINE] Status: {r.status_code}  preview: {r.text[:200]}")

            data  = r.json()
            items = data
            if isinstance(data, dict):
                for key in ("cantari", "songs", "results", "data"):
                    if key in data:
                        items = data[key]
                        break
                else:
                    vals = list(data.values())
                    items = vals[0] if vals else []
            if not isinstance(items, list):
                items = [items] if items else []

            results = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                title  = (item.get("titlu") or item.get("title") or item.get("nume") or "").strip()
                author = (item.get("autor") or item.get("author") or "").strip()
                raw    = (item.get("versuri") or item.get("lyrics") or
                          item.get("text")    or item.get("continut") or "")
                sid    = str(item.get("id") or item.get("song_id") or "")
                if not title:
                    continue
                slides = [b.strip() for b in str(raw).split("\n\n") if b.strip()] if raw else []
                results.append({
                    "title":   title,
                    "author":  author,
                    "song_id": sid,
                    "slides":  slides,
                    "content": "\n\n".join(slides),
                    "source":  "cantaricrestine.ro",
                    "url":     f"{API_BASE}?token={token}&id={sid}" if sid else "",
                })

            print(f"[ONLINE] API rezultate: {len(results)}")
            if results:
                self.results_ready.emit(results)
                return

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[ONLINE] API error: {e} — fallback scraping")

        # ── 2. Fallback: scraping resursecrestine.ro ─────────────────────────
        self._fallback_scraping()

    def _fallback_scraping(self):
        """
        Scrape resursecrestine.ro/cantece/?search=QUERY
        Links follow the pattern /cantece/<id>/<slug>
        """
        try:
            import requests
            from bs4 import BeautifulSoup

            q   = urllib.parse.quote(self.query)
            url = f"{RC_BASE}/cantece/?search={q}"
            print(f"[ONLINE] RC search: {url}")

            r    = requests.get(url, headers=_HEADERS, timeout=15)
            print(f"[ONLINE] Status: {r.status_code}")
            soup = BeautifulSoup(r.text, "html.parser")

            results: list[dict] = []
            seen_ids: set[str]  = set()
            _skip_nav = {
                "inainte", "înainte", "anterior", "urmator", "următor",
                "inapoi", "înapoi", "pagina", "pagina anterioara",
                "pagina urmatoare", "home", "acasa", "cauta", "meniu",
            }

            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                m    = re.search(r"/cantece/(\d+)/([^/\s\"?#]+)", href)
                if not m:
                    continue
                song_id = m.group(1)
                slug    = m.group(2)
                if song_id in seen_ids:
                    continue
                seen_ids.add(song_id)

                title = a.get_text(strip=True)
                # Try parent block for better title text
                if not title or len(title) < 3:
                    parent = a.find_parent(["div", "li", "td", "h2", "h3", "p"])
                    if parent:
                        title = parent.get_text(strip=True)[:80]
                if not title or len(title) < 3:
                    title = slug.replace("-", " ").title()
                if title.lower().strip() in _skip_nav:
                    continue

                results.append({
                    "title":   title,
                    "author":  "",
                    "song_id": song_id,
                    "slug":    slug,
                    "slides":  [],
                    "content": "",
                    "source":  "resursecrestine.ro",
                    "url":     f"{RC_BASE}/cantece/vizualizeaza-resursa/{song_id}",
                })
                if len(results) >= 25:
                    break

            print(f"[ONLINE] RC results: {len(results)}")
            if results:
                self.results_ready.emit(results)
            else:
                self.error.emit("Niciun rezultat găsit.\nÎncearcă alt termen.")

        except Exception as e:
            import traceback; traceback.print_exc()
            self.error.emit(str(e))


# ── Load Thread ───────────────────────────────────────────────────────────────

class LoadThread(QThread):
    loaded     = pyqtSignal(dict)
    from_cache = pyqtSignal(bool)   # backward-compat — emis dacă e din cache

    def __init__(self, url: str, song_id: str = "", source: str = ""):
        super().__init__()
        self.url     = url
        self.song_id = song_id
        self.source  = source

    def run(self):
        # Cache local
        cached = get_cached_song(self.url)
        if cached:
            _log.info("Din cache: %s", self.url)
            self.from_cache.emit(True)
            self.loaded.emit(cached)
            return
        self.from_cache.emit(False)

        if self.song_id and "cantaricrestine" in self.source:
            self._load_api()
        else:
            self._load_scraping()

    def _load_api(self):
        try:
            import requests
            token = random.randint(100_000, 999_999)
            url   = f"{API_BASE}?token={token}&id={self.song_id}"
            r     = requests.get(url, timeout=15)
            data  = r.json()

            item = data
            if isinstance(data, list) and data:
                item = data[0]
            elif isinstance(data, dict):
                for key in ("cantari", "songs", "data", "result"):
                    v = data.get(key)
                    if isinstance(v, list) and v:
                        item = v[0]; break
                    elif isinstance(v, dict):
                        item = v; break

            raw    = (item.get("versuri") or item.get("lyrics") or item.get("text") or "")
            title  = (item.get("titlu")   or item.get("title")  or "")
            author = (item.get("autor")   or item.get("author") or "")
            slides = [b.strip() for b in str(raw).split("\n\n") if b.strip()]
            if not slides and raw:
                slides = [str(raw).strip()]

            result = {
                "title": str(title), "author": str(author),
                "slides": slides, "content": "\n\n".join(slides),
                "source": "cantaricrestine.ro",
            }
            cache_song(self.url, result)
            self.loaded.emit(result)
        except Exception as e:
            import traceback; traceback.print_exc()
            self.loaded.emit({"title": "", "author": "",
                              "slides": [f"Eroare API: {e}"],
                              "content": "", "source": ""})

    def _load_scraping(self):
        """
        Load lyrics from the /cantece/vizualizeaza-resursa/<id> URL
        which returns a cleaner text-only page on resursecrestine.ro.
        """
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError as e:
            self.loaded.emit({"slides": [f"Lipsesc pachete: {e}"],
                              "content": "", "author": "", "title": ""})
            return

        try:
            r    = requests.get(self.url, headers=_HEADERS, timeout=15)
            print(f"[ONLINE] Load {self.url}: {r.status_code}")
            soup = BeautifulSoup(r.text, "html.parser")

            # ── Title ─────────────────────────────────────────────────────────
            title = ""
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
            if not title:
                for sel in ["h2", ".title", ".song-title", ".entry-title",
                            ".page-title", "#page-title"]:
                    el = soup.select_one(sel)
                    if el:
                        t2 = el.get_text(strip=True)
                        if t2 and len(t2) > 2:
                            title = t2; break

            # ── Author ────────────────────────────────────────────────────────
            author = ""
            al = soup.find_all("a", href=re.compile(r"/index-autori/|/autori/"))
            if al:
                author = al[0].get_text(strip=True)

            # ── Lyrics block — ordered by priority ────────────────────────────
            _lyric_selectors = [
                ".cantec-text", ".song-text", ".lyrics", ".versuri",
                "#versuri", ".resursa-text", ".content-text",
                ".resource-text", "#resource-content",
                ".resursa-content", ".text-cantec",
                "[class*='versuri']", "[class*='cantec']", "[class*='lyrics']",
                ".entry-content", "article",
            ]
            lyrics_el = None
            for sel in _lyric_selectors:
                try:
                    el = soup.select_one(sel)
                except Exception:
                    continue
                if el:
                    txt = el.get_text(strip=True)
                    if len(txt) > 30:
                        lyrics_el = el
                        print(f"[ONLINE] selector ok: {sel}")
                        break

            # Fallback: largest text block (skip nav/header/footer)
            if not lyrics_el:
                _skip_tags = {
                    "header", "footer", "nav", "menu", "sidebar",
                    "comment", "widget", "social", "share",
                    "related", "ad", "banner",
                }
                best = (0, None)
                for tag in soup.find_all(["div", "article", "section", "pre"]):
                    cls = " ".join(tag.get("class", []))
                    id_ = tag.get("id", "")
                    if any(s in cls.lower() or s in id_.lower()
                           for s in _skip_tags):
                        continue
                    lines = [l for l in
                             tag.get_text(separator="\n").splitlines()
                             if l.strip()]
                    if len(lines) > best[0]:
                        best = (len(lines), tag)
                if best[1]:
                    lyrics_el = best[1]

            if not lyrics_el:
                # Last resort: strip body
                body = soup.find("body")
                if body:
                    for tag in body.find_all(["script", "style", "nav",
                                              "header", "footer", "aside"]):
                        tag.decompose()
                    lyrics_el = body

            lyrics_text = lyrics_el.get_text(separator="\n") if lyrics_el else ""

            # ── Filter navigation noise ────────────────────────────────────────
            filtered: list[str] = []
            for line in lyrics_text.splitlines():
                line = line.strip()
                if not line:
                    filtered.append("")
                elif not any(p in line.lower() for p in _NAV_PHRASES):
                    filtered.append(line)
                else:
                    break   # stop at first nav phrase (everything after is UI)

            # ── Split into slides ──────────────────────────────────────────────
            slides: list[str] = []
            current: list[str] = []
            for line in filtered:
                if not line:
                    if current:
                        t3 = "\n".join(current).strip()
                        if len(t3) > 3:
                            slides.append(t3)
                        current = []
                else:
                    if _STANZA_MARKERS.match(line) and current:
                        t3 = "\n".join(current).strip()
                        if len(t3) > 3:
                            slides.append(t3)
                        current = []
                    current.append(line)
            if current:
                t3 = "\n".join(current).strip()
                if len(t3) > 3:
                    slides.append(t3)

            slides = [s for s in slides
                      if len(s.strip()) > 5
                      and not any(p in s.lower() for p in _NAV_PHRASES)]

            # Chunk fallback if still nothing
            if not slides:
                all_lines = [l for l in filtered if l]
                slides = ["\n".join(all_lines[i:i + 4])
                          for i in range(0, len(all_lines), 4)
                          if all_lines[i:i + 4]]

            print(f"[ONLINE] Extras: titlu='{title}' autor='{author}' slide-uri={len(slides)}")
            data = {"slides": slides, "content": "\n\n".join(slides),
                    "author": author, "title": title, "source": "resursecrestine.ro"}
            cache_song(self.url, data)
            _log.info("Cache-uit: %s (%d slides)", self.url, len(slides))
            self.loaded.emit(data)

        except Exception as e:
            import traceback; traceback.print_exc()
            _log.error("Load error %s: %s", self.url, e)
            self.loaded.emit({"title": "", "author": "",
                              "slides": [f"Eroare: {e}"],
                              "content": "", "source": ""})


# ── Online Songs Tab ──────────────────────────────────────────────────────────

class OnlineSongsTab(QWidget):
    """Tab UI for searching and importing songs from resursecrestine.ro."""

    # Emitted when user clicks "Trimite Live" — carries slide list
    send_live_requested = pyqtSignal(list, str, str)   # (slides, title, author)
    # Emitted when user clicks "Importă în bibliotecă"
    import_requested    = pyqtSignal(dict)             # song dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: list[dict] = []
        self._current_song: dict  = {}
        self._search_thread: SearchThread | None = None
        self._load_thread:   LoadThread   | None = None

        self._build_ui()

        # Connection indicator check (debounced 500ms after tab is shown)
        QTimer.singleShot(600, self._check_connection)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        # ── Top bar: header + connection indicator on same row ─────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        hdr = QLabel("🌐 cantaricrestine.ro + resursecrestine.ro")
        hdr.setStyleSheet("color:#5294e2; font-size:12px; font-weight:700;")
        top_row.addWidget(hdr)
        top_row.addStretch()
        self._conn_dot = QLabel("●")
        self._conn_dot.setStyleSheet("color:#555; font-size:12px;")
        self._conn_label = QLabel("Verifică…")
        self._conn_label.setStyleSheet("color:#555; font-size:10px;")
        top_row.addWidget(self._conn_dot)
        top_row.addWidget(self._conn_label)
        root.addLayout(top_row)

        # ── Search bar ─────────────────────────────────────────────────────
        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Caută cântare (ex: Doamne Tu ești)…")
        self._search_edit.setStyleSheet(
            "QLineEdit { background:#1a1a1a; color:#e0e0e0; border:1px solid #333; "
            "border-radius:4px; padding:5px 8px; font-size:11px; }"
            "QLineEdit:focus { border-color:#5294e2; }"
        )
        self._search_edit.returnPressed.connect(self._do_search)
        search_row.addWidget(self._search_edit, 1)

        self._search_btn = QPushButton("🔍")
        self._search_btn.setFixedWidth(32)
        self._search_btn.setFixedHeight(28)
        self._search_btn.setStyleSheet(
            "QPushButton { background:#18283a; color:#5294e2; border:1px solid #1c3a5a; "
            "border-radius:4px; font-size:14px; padding:2px; }"
            "QPushButton:hover { background:#1c3a5a; color:#fff; }"
        )
        self._search_btn.clicked.connect(self._do_search)
        search_row.addWidget(self._search_btn)
        root.addLayout(search_row)

        # ── Status + cache indicator on same row ───────────────────────────
        st_row = QHBoxLayout()
        st_row.setSpacing(8)
        self._status_lbl = QLabel("Introdu un termen și apasă 🔍")
        self._status_lbl.setStyleSheet("color:#555; font-size:10px;")
        st_row.addWidget(self._status_lbl, 1)
        self._cache_lbl = QLabel("")
        self._cache_lbl.setStyleSheet("color:#666; font-size:10px; font-style:italic;")
        self._cache_lbl.hide()
        st_row.addWidget(self._cache_lbl)
        root.addLayout(st_row)

        # ── Results list ───────────────────────────────────────────────────
        self._results_list = QListWidget()
        self._results_list.setStyleSheet(
            "QListWidget { background:#141414; border:1px solid #222; border-radius:4px; }"
            "QListWidget::item { padding:5px 8px; color:#ccc; border-radius:3px; }"
            "QListWidget::item:hover { background:#1c1c1c; }"
            "QListWidget::item:selected { background:#1c3a5a; color:#e0e0e0; }"
        )
        self._results_list.setFixedHeight(120)
        self._results_list.itemClicked.connect(self._on_result_clicked)
        root.addWidget(self._results_list)

        # ── Preview ────────────────────────────────────────────────────────
        self._preview_edit = QTextEdit()
        self._preview_edit.setReadOnly(True)
        self._preview_edit.setFont(QFont("Consolas", 9))
        self._preview_edit.setPlaceholderText("Selectează o cântare din listă pentru preview…")
        self._preview_edit.setStyleSheet(
            "QTextEdit { background:#0d1218; color:#cccccc; border:1px solid #1c2a3a; "
            "border-radius:4px; padding:4px; font-size:10px; }"
        )
        root.addWidget(self._preview_edit, 1)

        # ── Action buttons ─────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        _btn_ss = (
            "QPushButton {{ background:{bg}; color:{fg}; border:1px solid {bd}; "
            "border-radius:4px; padding:5px 10px; font-size:11px; font-weight:600; }}"
            "QPushButton:hover {{ background:{hbg}; color:#fff; }}"
            "QPushButton:disabled {{ color:#333; border-color:#1a1a1a; background:#111; }}"
        )
        self._import_btn = QPushButton("💾 Importă")
        self._import_btn.setEnabled(False)
        self._import_btn.setStyleSheet(
            _btn_ss.format(bg="#18283a", fg="#5294e2", bd="#1c3a5a",
                           hbg="#1c3a5a", hfg="#fff")
        )
        self._import_btn.clicked.connect(self._import_song)
        btn_row.addWidget(self._import_btn)

        self._live_btn = QPushButton("▶ Live")
        self._live_btn.setEnabled(False)
        self._live_btn.setStyleSheet(
            _btn_ss.format(bg="#1a3d1a", fg="#a6e3a1", bd="#3a7a3a",
                           hbg="#1e4d1e", hfg="#fff")
        )
        self._live_btn.clicked.connect(self._send_live)
        btn_row.addWidget(self._live_btn)

        self._clear_cache_btn = QPushButton("🗑")
        self._clear_cache_btn.setFixedWidth(32)
        self._clear_cache_btn.setToolTip("Golește cache-ul de cântări online")
        self._clear_cache_btn.setStyleSheet(
            "QPushButton { background:#1a1a1a; color:#555; border:1px solid #222; "
            "border-radius:4px; padding:5px; font-size:12px; }"
            "QPushButton:hover { background:#1c1c1c; color:#f38ba8; border-color:#f38ba8; }"
        )
        self._clear_cache_btn.clicked.connect(self._clear_cache)
        btn_row.addWidget(self._clear_cache_btn)

        root.addLayout(btn_row)

    # ── Connection check ──────────────────────────────────────────────────────

    def _check_connection(self):
        import threading

        def _run():
            try:
                import requests
                r = requests.get(BASE_URL, headers=_HEADERS, timeout=6)
                ok = r.status_code == 200
            except Exception:
                ok = False

            def _update():
                if ok:
                    self._conn_dot.setStyleSheet("color:#a6e3a1; font-size:14px;")
                    self._conn_label.setText("● resursecrestine.ro")
                    self._conn_label.setStyleSheet("color:#a6e3a1; font-size:11px;")
                else:
                    self._conn_dot.setStyleSheet("color:#f38ba8; font-size:14px;")
                    self._conn_label.setText("Fără conexiune internet")
                    self._conn_label.setStyleSheet("color:#f38ba8; font-size:11px;")

            QTimer.singleShot(0, _update)

        threading.Thread(target=_run, daemon=True).start()

    # ── Search ────────────────────────────────────────────────────────────────

    def _do_search(self):
        query = self._search_edit.text().strip()
        if not query:
            return
        if self._search_thread and self._search_thread.isRunning():
            self._search_thread.quit()

        self._results_list.clear()
        self._results = []
        self._preview_edit.clear()
        self._import_btn.setEnabled(False)
        self._live_btn.setEnabled(False)
        self._status_lbl.setText("⏳ Se caută…")
        self._search_btn.setEnabled(False)

        self._search_thread = SearchThread(query)
        self._search_thread.results_ready.connect(self._on_results)
        self._search_thread.error.connect(self._on_search_error)
        self._search_thread.finished.connect(lambda: self._search_btn.setEnabled(True))
        self._search_thread.start()

    def _on_results(self, results: list):
        self._results = results
        self._results_list.clear()
        for r in results:
            item = QListWidgetItem(r["title"])
            item.setData(Qt.ItemDataRole.UserRole, r["url"])
            self._results_list.addItem(item)
        n = len(results)
        self._status_lbl.setText(f"✓ {n} rezultat{'e' if n != 1 else ''} găsite")

    def _on_search_error(self, msg: str):
        self._status_lbl.setText(f"✗ {msg}")

    # ── Result selection & lyrics loading ─────────────────────────────────────

    def _on_result_clicked(self, item: QListWidgetItem):
        idx = self._results_list.row(item)
        if idx < 0 or idx >= len(self._results):
            return
        result = self._results[idx]
        self._current_song = result
        self._import_btn.setEnabled(False)
        self._live_btn.setEnabled(False)

        # If slides already loaded (e.g. from previous click), show directly
        if result.get("slides"):
            preview = "\n\n---\n\n".join(result["slides"])
            self._preview_edit.setPlainText(preview)
            self._import_btn.setEnabled(True)
            self._live_btn.setEnabled(True)
            return

        self._preview_edit.setPlainText("⏳ Se încarcă versurile…")
        self._status_lbl.setText("⏳ Se încarcă versurile...")

        if self._load_thread and self._load_thread.isRunning():
            self._load_thread.quit()

        self._load_thread = LoadThread(
            result["url"],
            result.get("song_id", ""),
            result.get("source", ""),
        )
        self._load_thread.loaded.connect(self._on_loaded)
        self._load_thread.from_cache.connect(self._on_cache_indicator)
        self._load_thread.start()

    def _on_loaded(self, data: dict):
        self._current_song.update(data)
        slides = data.get("slides", [])
        content = data.get("content", "")
        if not content:
            content = "\n\n".join(slides)
        self._preview_edit.setPlainText(content or "Nu s-au putut extrage versurile.")
        has_content = bool(slides and any(s.strip() for s in slides))
        self._import_btn.setEnabled(has_content)
        self._live_btn.setEnabled(has_content)
        # Update title/author if the page provided them
        if data.get("title") and not self._current_song.get("title"):
            self._current_song["title"] = data["title"]
        if data.get("author"):
            self._current_song["author"] = data["author"]

    def _on_cache_indicator(self, is_cached: bool):
        """Show cache source indicator below status label."""
        if is_cached:
            self._cache_lbl.setText("📦 Din cache local (< 24h)")
            self._cache_lbl.setStyleSheet("color:#a6e3a1; font-size:10px; font-style:italic;")
        else:
            self._cache_lbl.setText("🌐 Descărcat de pe internet")
            self._cache_lbl.setStyleSheet("color:#5294e2; font-size:10px; font-style:italic;")
        self._cache_lbl.show()

    def _clear_cache(self):
        clear_online_cache()
        self._status_lbl.setText("🗑 Cache golit")
        self._cache_lbl.hide()
        try:
            from toast_notifications import show_toast
            show_toast("🗑 Cache online golit!", "info")
        except Exception:
            pass

    # ── Actions ───────────────────────────────────────────────────────────────

    def _import_song(self):
        song = self._current_song
        if not song:
            return
        import database as db
        title   = song.get("title", "Cântare online")
        content = song.get("content") or "\n\n".join(song.get("slides", []))
        slides  = song.get("slides", [s.strip() for s in content.split("\n\n") if s.strip()])
        author  = song.get("author", "")
        notes   = f"Sursă: resursecrestine.ro\n{song.get('url', '')}"

        try:
            song_id = db.add_song(
                title=title, content=content, slides=slides,
                author=author, category="Online", notes=notes,
            )
            self._status_lbl.setText(f"✓ «{title}» importată în bibliotecă (ID {song_id})")
            try:
                from toast_notifications import show_toast
                show_toast(f"💾 «{title}» importată!", "success")
            except Exception:
                pass
            self.import_requested.emit({
                "title": title, "author": author, "category": "Online",
                "content": content, "slides": slides, "notes": notes,
            })
        except Exception as e:
            self._status_lbl.setText(f"✗ Import eșuat: {e}")

    def _send_live(self):
        song = self._current_song
        if not song:
            return
        slides = song.get("slides", [])
        if not slides:
            content = song.get("content", "")
            slides  = [s.strip() for s in content.split("\n\n") if s.strip()]
        if slides:
            self.send_live_requested.emit(
                slides,
                song.get("title", ""),
                song.get("author", ""),
            )
            try:
                from toast_notifications import show_toast
                show_toast("▶ Trimis Live!", "success")
            except Exception:
                pass
