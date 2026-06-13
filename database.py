"""
Cantio - Database Manager (v3 — split files)
songs.db       — SQLite — cântări
bible.db       — SQLite — cărți și versete biblice
settings.json  — JSON  — setările aplicației
playlists.json — JSON  — playlist / serviciu
presentations.json — JSON — prezentări
stage.json     — JSON  — layout-uri stage monitor
cache.json     — JSON  — fișiere recente, preferințe UI

Migrare automată din cantio.db monolitic la prima pornire.
"""
import sqlite3
import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path

from paths import get_data_dir, get_profile_dir

_log = logging.getLogger("Cantio.db")

# ── Global paths (set by set_active_profile) ──────────────────────────────────
_active_profile = None
_profile_dir = None
_songs_db_path = None
_bible_db_path = None
_settings_path = None
_playlists_path = None
_presentations_path = None
_stage_path = None
_cache_path = None

# Legacy compat symbols (updated by set_active_profile)
DB_PATH = os.path.join(get_data_dir(), "cantio.db")
CACHE_DIR = os.path.join(get_data_dir(), "cache")

# Default settings dict
_SETTINGS_DEFAULTS = {
    "display_screen": "1",
    "stage_screen": "2",
    "bg_color": "#000000",
    "text_color": "#ffffff",
    "font_family": "Arial",
    "font_size": "48",
    "font_bold": "true",
    "font_italic": "false",
    "text_shadow": "true",
    "line_spacing": "1.4",
    "margin": "60",
    "transition": "fade",
    "outline_color": "#000000",
    "outline_width": "2",
    "bg_image": "",
    "bg_opacity": "0.5",
    "bg_video": "",
    "bg_video_opacity": "1.0",
    "ticker_text": "",
    "ticker_enabled": "false",
    "ticker_speed": "2",
    "ticker_color": "#ffffff",
    "ticker_bg": "#000000cc",
    "clock_enabled": "false",
    "clock_color": "#ffffff",
    "clock_format": "HH:MM:SS",
    "countdown_enabled": "false",
    "countdown_seconds": "300",
    "countdown_color": "#ffffff",
    "text_align": "center",
    "text_valign": "center",
    "auto_advance": "false",
    "auto_advance_seconds": "5",
    "supabase_url": "",
    "supabase_key": "",
    "supabase_bucket": "cantio-media",
    "stage_layout": "[]",
    "sacred_words": "Jesus,Isus,Iisus,God,Dumnezeu,Hristos,Christ,Domnul,Holy Spirit,Duhul Sfânt,Emanuel,Tatăl,Fiul,Mesia,Aleluia,Amin",
    "sacred_words_enabled": "false",
    "sacred_words_allcaps": "false",
    "thumb_size": "S",
    "language": "ro",
    "performance_mode": "false",
    "copyright": '{"enabled": false, "mode": "title_author", "custom_text": "", "position": "bottom_right", "font_size": 12, "color": "#ffffff", "opacity": 0.4}',
}


# ── Profile management ────────────────────────────────────────────────────────

def set_active_profile(name):
    global DB_PATH, CACHE_DIR, _active_profile, _profile_dir
    global _songs_db_path, _bible_db_path, _settings_path
    global _playlists_path, _presentations_path, _stage_path, _cache_path

    _active_profile = name
    _profile_dir = get_profile_dir(name)
    os.makedirs(_profile_dir, exist_ok=True)

    _songs_db_path = os.path.join(_profile_dir, "songs.db")
    _bible_db_path = os.path.join(_profile_dir, "bible.db")
    _settings_path = os.path.join(_profile_dir, "settings.json")
    _playlists_path = os.path.join(_profile_dir, "playlists.json")
    _presentations_path = os.path.join(_profile_dir, "presentations.json")
    _stage_path = os.path.join(_profile_dir, "stage.json")
    _cache_path = os.path.join(_profile_dir, "cache.json")

    # Legacy compat
    DB_PATH = os.path.join(_profile_dir, "cantio.db")
    CACHE_DIR = os.path.join(_profile_dir, "cache")


def get_active_profile():
    return _active_profile


# ── Connection factories ──────────────────────────────────────────────────────

def _apply_pragmas(conn: sqlite3.Connection) -> sqlite3.Connection:
    """
    Apply performance-critical SQLite PRAGMAs.
    WAL mode alone can give 3-5× faster concurrent reads on large DBs.
    busy_timeout=30000 tells SQLite to wait up to 30 s instead of
    raising "database is locked" immediately.
    """
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")    # 10 000 × 4 KB = ~40 MB page cache
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456") # 256 MB memory-mapped I/O
    conn.execute("PRAGMA busy_timeout=30000")  # wait 30 s before "locked" error
    return conn


def get_songs_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_songs_db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return _apply_pragmas(conn)


def get_bible_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_bible_db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return _apply_pragmas(conn)


def get_bible_db_for_profile(profile: str = "default") -> sqlite3.Connection:
    """
    Open (and initialise if needed) a per-profile bible.db.
    Supports multiple translations per profile via bible_translations table.
    """
    import os as _os
    from paths import get_profile_dir as _gpd
    profile_dir = _gpd(profile)
    _os.makedirs(profile_dir, exist_ok=True)
    db_path = _os.path.join(profile_dir, "bible.db")

    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS bible_translations (
            id          INTEGER PRIMARY KEY,
            name        TEXT UNIQUE,
            abbreviation TEXT,
            language    TEXT DEFAULT 'ro',
            is_active   INTEGER DEFAULT 1,
            is_secondary INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bible_books (
            id             INTEGER PRIMARY KEY,
            book_id        INTEGER,
            name           TEXT,
            abbreviation   TEXT,
            testament      TEXT,
            book_order     INTEGER,
            translation_id INTEGER,
            FOREIGN KEY (translation_id) REFERENCES bible_translations(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bible_verses (
            id             INTEGER PRIMARY KEY,
            book_id        INTEGER,
            chapter        INTEGER,
            verse          INTEGER,
            text           TEXT,
            translation_id INTEGER,
            FOREIGN KEY (translation_id) REFERENCES bible_translations(id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_verses_lookup
        ON bible_verses (translation_id, book_id, chapter, verse)
    """)
    conn.commit()
    return conn


def get_available_translations(profile: str = "default") -> list[dict]:
    """Return list of translation dicts {id, name, abbreviation} for a profile."""
    try:
        conn = get_bible_db_for_profile(profile)
        rows = conn.execute(
            "SELECT id, name, abbreviation FROM bible_translations ORDER BY id"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def import_bible_to_profile(
    books: list,
    verses: list,
    translation_name: str,
    abbreviation: str = "",
    profile: str = "default",
) -> int:
    """
    Import a Bible translation into a per-profile database.
    Returns the translation_id.
    Overwrites existing data if translation_name already exists.
    """
    conn = get_bible_db_for_profile(profile)
    try:
        existing = conn.execute(
            "SELECT id FROM bible_translations WHERE name=?",
            (translation_name,)
        ).fetchone()

        if existing:
            translation_id = existing[0]
            conn.execute(
                "DELETE FROM bible_verses WHERE translation_id=?", (translation_id,)
            )
            conn.execute(
                "DELETE FROM bible_books WHERE translation_id=?", (translation_id,)
            )
        else:
            conn.execute(
                "INSERT INTO bible_translations (name, abbreviation) VALUES (?, ?)",
                (translation_name, abbreviation or translation_name[:5])
            )
            translation_id = conn.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]

        for book in books:
            conn.execute(
                """INSERT INTO bible_books
                   (book_id, name, abbreviation, testament, book_order, translation_id)
                   VALUES (?,?,?,?,?,?)""",
                (
                    book["id"],
                    book["name"],
                    book.get("abbreviation", ""),
                    book.get("testament", "OT"),
                    book.get("book_order", book["id"]),
                    translation_id,
                )
            )

        conn.executemany(
            """INSERT INTO bible_verses
               (book_id, chapter, verse, text, translation_id)
               VALUES (?,?,?,?,?)""",
            [
                (v["book_id"], v["chapter"], v["verse"], v["text"], translation_id)
                for v in verses
            ]
        )
        conn.commit()
        print(f"[Bible] Importat {len(verses)} versete în profilul '{profile}'")
        return translation_id
    finally:
        conn.close()


def get_verses_for_translation(
    book_id: int,
    chapter:  int,
    translation_id: int,
    profile: str = "default",
) -> list[dict]:
    """Fetch verses for a specific translation_id from the per-profile bible."""
    try:
        conn = get_bible_db_for_profile(profile)
        rows = conn.execute(
            """SELECT * FROM bible_verses
               WHERE book_id=? AND chapter=? AND translation_id=?
               ORDER BY verse""",
            (book_id, chapter, translation_id)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_connection() -> sqlite3.Connection:
    """Legacy compat — returns songs DB connection."""
    return get_songs_db()


def ensure_fts_populated():
    """
    Verify that songs_fts has at least as many rows as songs.
    Re-inserts if empty (e.g. after a manual DB copy or schema reset).
    Safe to call multiple times — idempotent.
    """
    conn = None
    try:
        conn = get_songs_db()
        fts_count = conn.execute(
            "SELECT COUNT(*) AS c FROM songs_fts"
        ).fetchone()["c"]
        songs_count = conn.execute(
            "SELECT COUNT(*) AS c FROM songs"
        ).fetchone()["c"]

        if fts_count < songs_count:
            print(f"[DB] FTS5 desync ({fts_count}/{songs_count}), repopulating…")
            conn.execute("DELETE FROM songs_fts")
            conn.execute("""
                INSERT INTO songs_fts(rowid, title, author)
                SELECT id, COALESCE(title,''), COALESCE(author,'') FROM songs
            """)
            conn.commit()
            print("[DB] FTS5 repopulated OK")
    except Exception as e:
        print(f"[DB] ensure_fts_populated: {e}")
        # FTS table might be missing entirely — recreate
        try:
            if conn:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS songs_fts USING fts5(
                        title, author,
                        content='songs', content_rowid='id',
                        tokenize='unicode61 remove_diacritics 2'
                    )
                """)
                conn.execute("""
                    INSERT INTO songs_fts(rowid, title, author)
                    SELECT id, COALESCE(title,''), COALESCE(author,'') FROM songs
                """)
                conn.commit()
        except Exception as e2:
            print(f"[DB] FTS recreate failed: {e2}")
    finally:
        if conn:
            conn.close()


def reindex_fts5() -> int:
    """
    Recreează complet indexul FTS5 din songs.
    Returnează numărul de cântări reindexate.
    """
    conn = None
    try:
        conn = get_songs_db()
        _log.info("Reindexare FTS5 pornită…")
        conn.execute("DELETE FROM songs_fts")
        conn.execute("""
            INSERT INTO songs_fts(rowid, title, author)
            SELECT id,
                   LOWER(COALESCE(title,  '')),
                   LOWER(COALESCE(author, ''))
            FROM songs
        """)
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM songs_fts"
        ).fetchone()["c"]
        _log.info("FTS5 reindexat: %d cântări", count)
        print(f"[DB] FTS5 reindexat: {count} cântări")
        return count
    except Exception as e:
        _log.error("Reindex FTS5 error: %s", e)
        print(f"[DB] Reindex error: {e}")
        return 0
    finally:
        if conn:
            conn.close()


def needs_reindex() -> bool:
    """
    Returnează True dacă songs_fts are mai puține înregistrări decât songs.
    Folosit la pornire pentru a detecta desincronizarea indexului.
    """
    try:
        conn = get_songs_db()
        songs_count = conn.execute(
            "SELECT COUNT(*) AS c FROM songs"
        ).fetchone()["c"]
        fts_count = conn.execute(
            "SELECT COUNT(*) AS c FROM songs_fts"
        ).fetchone()["c"]
        conn.close()
        return fts_count < songs_count
    except Exception:
        return True


def normalize_text(text: str) -> str:
    """
    Remove Romanian diacritics and lowercase — used for accent-insensitive search.
    ș/ş→s  ț/ţ→t  î→i  ă→a  â→a
    """
    if not text:
        return ""
    rep = {
        'ș': 's', 'Ș': 's', 'ş': 's', 'Ş': 's',
        'ț': 't', 'Ț': 't', 'ţ': 't', 'Ţ': 't',
        'î': 'i', 'Î': 'i',
        'ă': 'a', 'Ă': 'a',
        'â': 'a', 'Â': 'a',
    }
    result = text.lower()
    for orig, repl in rep.items():
        result = result.replace(orig, repl)
    return result


def normalize_search_query(query: str) -> str:
    """Prepare a search query for accent-insensitive, hyphen-tolerant matching.

    Steps:
    1. Apply Romanian diacritic→ASCII mapping (via normalize_text)
    2. Replace hyphens with spaces (so "fii-mi" matches "fii mi" or "fiimi")
    3. Collapse multiple spaces
    4. Strip leading/trailing whitespace
    The result is lower-case ASCII suitable for LIKE comparisons.
    """
    import re
    if not query:
        return ""
    normalized = normalize_text(query)          # diacritics → ASCII, lowercase
    normalized = normalized.replace('-', ' ')   # hyphens → spaces
    normalized = re.sub(r'[^\w\s]', ' ', normalized)  # strip other punctuation
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def execute_with_retry(conn: sqlite3.Connection, sql: str,
                       params=(), retries: int = 5):
    """
    Execute a write statement with exponential-backoff retry on lock errors.
    Commits after each successful execution.
    """
    for attempt in range(retries):
        try:
            result = conn.execute(sql, params)
            conn.commit()
            return result
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < retries - 1:
                time.sleep(0.1 * (attempt + 1))
                continue
            raise


def check_and_repair_db():
    """Verifică integritatea DB la pornire și repară dacă e coruptă."""
    conn = None
    try:
        conn = get_songs_db()
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if result and result[0] != "ok":
            _log.error("DB coruptă: %s — se încearcă reparare…", result[0])
            print(f"[DB] Coruptă: {result[0]} — se încearcă reparare...")
            conn.close()
            conn = None
            _repair_db()
        else:
            _log.info("Integritate DB OK")
            print("[DB] Integritate OK")
    except Exception as e:
        _log.error("integrity_check eșuat: %s — se încearcă reparare…", e)
        print(f"[DB] integrity_check eșuat: {e} — se încearcă reparare...")
        try:
            if conn:
                conn.close()
                conn = None
        except Exception:
            pass
        _repair_db()
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def _repair_db():
    """Încearcă să repare DB coruptă prin SQLite backup API."""
    import shutil
    db_path = _songs_db_path
    if not db_path or not os.path.exists(db_path):
        print("[DB] Repair: calea DB nu e setată sau fișierul nu există — se sare.")
        return
    backup_path = db_path + ".backup"
    new_path = db_path + ".new"
    _log.info("Încearcă reparare DB prin backup API…")
    print("[DB] Încearcă reparare prin backup API...")
    try:
        # Keep a copy of the possibly-corrupt file just in case
        shutil.copy2(db_path, backup_path)
    except Exception as e:
        print(f"[DB] Nu s-a putut face backup: {e}")

    old_conn = new_conn = None
    try:
        old_conn = sqlite3.connect(db_path, timeout=5)
        new_conn = sqlite3.connect(new_path)
        old_conn.backup(new_conn)          # copies only readable pages
        old_conn.close(); old_conn = None
        new_conn.close(); new_conn = None
        os.replace(new_path, db_path)
        print("[DB] Reparare reușită!")
    except Exception as e:
        print(f"[DB] Reparare prin backup eșuată: {e}")
        # Last resort: delete corrupt file so init_db() can create a fresh one
        try:
            if old_conn:
                old_conn.close()
            if new_conn:
                new_conn.close()
            if os.path.exists(new_path):
                os.remove(new_path)
            broken_path = db_path + ".broken"
            os.rename(db_path, broken_path)
            print(f"[DB] DB coruptă mutată la: {broken_path}. Se va crea una nouă.")
        except Exception as e2:
            print(f"[DB] Repair cleanup error: {e2}")


# ── JSON helpers ──────────────────────────────────────────────────────────────

def _write_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_json(path: str, default):
    if not path or not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ── Database initialization ───────────────────────────────────────────────────

def init_db():
    # Auto-initialize default profile if none has been set yet
    if _songs_db_path is None:
        set_active_profile("default")
    # ── songs.db ──────────────────────────────────────────────────────────────
    conn = get_songs_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT DEFAULT '',
            category TEXT DEFAULT 'General',
            language TEXT DEFAULT 'ro',
            content TEXT NOT NULL,
            slides TEXT NOT NULL,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for col, defval in [("notes", "''"), ("author", "''"), ("category", "'General'"),
                        ("language", "'ro'"), ("formatting", "NULL"),
                        ("translations", "NULL")]:
        try:
            c.execute(f"ALTER TABLE songs ADD COLUMN {col} TEXT DEFAULT {defval}")
        except Exception:
            pass

    # Performance indexes — critical for 22k+ songs
    c.execute("CREATE INDEX IF NOT EXISTS idx_songs_title    ON songs(title COLLATE NOCASE)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_songs_category ON songs(category)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_songs_title_category ON songs(category, title COLLATE NOCASE)")

    # ── FTS5 full-text search — <10ms on 22k rows ─────────────────────────────
    # FTS5 is built into SQLite 3.9+ (ships with Python 3.8+)
    try:
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS songs_fts USING fts5(
                title,
                author,
                content='songs',
                content_rowid='id',
                tokenize='unicode61 remove_diacritics 2'
            )
        """)
        # Populate on first creation (idempotent — IF NOT EXISTS above guards re-runs)
        already = conn.execute(
            "SELECT COUNT(*) AS n FROM songs_fts"
        ).fetchone()["n"]
        if already == 0:
            c.execute("""
                INSERT INTO songs_fts(rowid, title, author)
                SELECT id, title, author FROM songs
            """)
        # Keep FTS in sync via triggers
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS songs_fts_insert
            AFTER INSERT ON songs BEGIN
                INSERT INTO songs_fts(rowid, title, author)
                VALUES (new.id, new.title, new.author);
            END
        """)
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS songs_fts_update
            AFTER UPDATE ON songs BEGIN
                INSERT INTO songs_fts(songs_fts, rowid, title, author)
                VALUES ('delete', old.id, old.title, old.author);
                INSERT INTO songs_fts(rowid, title, author)
                VALUES (new.id, new.title, new.author);
            END
        """)
        c.execute("""
            CREATE TRIGGER IF NOT EXISTS songs_fts_delete
            AFTER DELETE ON songs BEGIN
                INSERT INTO songs_fts(songs_fts, rowid, title, author)
                VALUES ('delete', old.id, old.title, old.author);
            END
        """)
    except Exception as _fts_err:
        pass   # FTS5 not compiled in — fall back to LIKE search

    # ── Normalized search columns (diacritics-free) ──────────────────────────
    # Each ALTER TABLE in its own try/except so one failure doesn't abort the rest
    for col_name, col_def in [
        ("title_normalized",  "TEXT DEFAULT ''"),
        ("author_normalized", "TEXT DEFAULT ''"),
    ]:
        try:
            c.execute(f"ALTER TABLE songs ADD COLUMN {col_name} {col_def}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists — that's fine

    # Populate normalized columns — wrapped separately so a malformed DB row
    # doesn't abort the whole startup sequence
    try:
        c.execute("""
            UPDATE songs
            SET title_normalized  = LOWER(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(title,
                'ș','s'),'Ș','s'),'ş','s'),'Ş','s'),
                'ț','t'),'Ț','t'),'ţ','t'),'Ţ','t'),
                'î','i'),'Î','i'),
                'ă','a'),'Ă','a'),
                'â','a'),'Â','a')),
                author_normalized = LOWER(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(author,''),
                'ș','s'),'Ș','s'),'ş','s'),'Ş','s'),
                'ț','t'),'Ț','t'),'ţ','t'),'Ţ','t'),
                'î','i'),'Î','i'),
                'ă','a'),'Ă','a'),
                'â','a'),'Â','a'))
            WHERE title_normalized IS NULL OR title_normalized = ''
               OR title LIKE '%ă%' OR title LIKE '%Ă%'
               OR title LIKE '%â%' OR title LIKE '%Â%'
        """)
        conn.commit()
    except Exception as _norm_err:
        print(f"[DB] Normalized column update skipped: {_norm_err}")
        # Non-fatal — search will fall back to LOWER(title) LIKE queries

    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_title_norm  ON songs(title_normalized)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_author_norm ON songs(author_normalized)")
        conn.commit()
    except Exception:
        pass  # indexes are optional

    conn.commit()
    conn.close()

    # ── Verify / repopulate FTS5 ──────────────────────────────────────────────
    ensure_fts_populated()

    # ── bible.db ──────────────────────────────────────────────────────────────
    conn = get_bible_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bible_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            abbreviation TEXT NOT NULL,
            testament TEXT NOT NULL,
            book_order INTEGER NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bible_verses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            text TEXT NOT NULL,
            translation TEXT DEFAULT 'VBA',
            FOREIGN KEY (book_id) REFERENCES bible_books(id)
        )
    """)
    conn.commit()
    conn.close()

    # ── settings.json ─────────────────────────────────────────────────────────
    if not os.path.exists(_settings_path):
        _write_json(_settings_path, dict(_SETTINGS_DEFAULTS))
    else:
        # Insert any new default keys not yet in the file
        existing = _read_json(_settings_path, {})
        changed = False
        for k, v in _SETTINGS_DEFAULTS.items():
            if k not in existing:
                existing[k] = v
                changed = True
        if changed:
            _write_json(_settings_path, existing)

    # ── playlists.json ────────────────────────────────────────────────────────
    if not os.path.exists(_playlists_path):
        _write_json(_playlists_path, {"next_id": 1, "items": []})

    # ── presentations.json ────────────────────────────────────────────────────
    if not os.path.exists(_presentations_path):
        _write_json(_presentations_path, {"next_id": 1, "items": []})

    # ── stage.json ────────────────────────────────────────────────────────────
    if not os.path.exists(_stage_path):
        _write_json(_stage_path, {})

    # ── cache.json ────────────────────────────────────────────────────────────
    if not os.path.exists(_cache_path):
        _write_json(_cache_path, {"recent_files": []})

    os.makedirs(CACHE_DIR, exist_ok=True)

    # ── migration ─────────────────────────────────────────────────────────────
    _migrate_from_monolithic()


# ── Migration ─────────────────────────────────────────────────────────────────

def _migrate_from_monolithic() -> bool:
    """Migrate data from old cantio.db to split files. Returns True on success."""
    old_db = DB_PATH  # points to cantio.db in profile dir
    if not os.path.exists(old_db):
        return True

    try:
        old = sqlite3.connect(old_db)
        old.row_factory = sqlite3.Row

        def _row(r) -> dict:
            """Convert sqlite3.Row to plain dict (Row has no .get())."""
            return dict(r)

        # ── songs ─────────────────────────────────────────────────────────────
        songs_conn = get_songs_db()
        existing_titles = {
            r["title"]
            for r in songs_conn.execute("SELECT title FROM songs").fetchall()
        }
        old_id_to_new_id: dict[int, int] = {}
        for row in [_row(r) for r in old.execute("SELECT * FROM songs").fetchall()]:
            if row["title"] not in existing_titles:
                cur = songs_conn.cursor()
                cur.execute(
                    "INSERT INTO songs (title, author, category, language, content, slides, notes)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (row["title"], row.get("author", ""), row.get("category", "General"),
                     row.get("language", "ro"), row["content"], row["slides"],
                     row.get("notes", ""))
                )
                new_id = cur.lastrowid
                old_id_to_new_id[row["id"]] = new_id
            else:
                new_row = songs_conn.execute(
                    "SELECT id FROM songs WHERE title=?", (row["title"],)
                ).fetchone()
                if new_row:
                    old_id_to_new_id[row["id"]] = new_row["id"]
        songs_conn.commit()
        songs_conn.close()

        # ── settings ──────────────────────────────────────────────────────────
        try:
            old_settings = {
                r["key"]: r["value"]
                for r in old.execute("SELECT key, value FROM settings").fetchall()
            }
            current = _read_json(_settings_path, dict(_SETTINGS_DEFAULTS))
            merged = dict(_SETTINGS_DEFAULTS)
            merged.update(old_settings)
            # Keys already customised in the new-format file win
            merged.update({k: v for k, v in current.items()
                           if k not in _SETTINGS_DEFAULTS or v != _SETTINGS_DEFAULTS[k]})
            _write_json(_settings_path, merged)
        except Exception:
            pass

        # ── bible ─────────────────────────────────────────────────────────────
        try:
            books = [_row(r) for r in old.execute("SELECT * FROM bible_books").fetchall()]
            verses = [_row(r) for r in old.execute("SELECT * FROM bible_verses").fetchall()]
            if books:
                bible_conn = get_bible_db()
                if bible_conn.execute("SELECT COUNT(*) FROM bible_books").fetchone()[0] == 0:
                    for b in books:
                        bible_conn.execute(
                            "INSERT INTO bible_books (id, name, abbreviation, testament, book_order)"
                            " VALUES (?,?,?,?,?)",
                            (b["id"], b["name"], b["abbreviation"], b["testament"], b["book_order"])
                        )
                    for v in verses:
                        bible_conn.execute(
                            "INSERT INTO bible_verses (book_id, chapter, verse, text, translation)"
                            " VALUES (?,?,?,?,?)",
                            (v["book_id"], v["chapter"], v["verse"], v["text"],
                             v.get("translation", "VBA"))
                        )
                    bible_conn.commit()
                bible_conn.close()
        except Exception:
            pass

        # ── playlist ──────────────────────────────────────────────────────────
        try:
            pl_rows = [_row(r) for r in old.execute(
                "SELECT id, song_id, position, label FROM playlist ORDER BY position"
            ).fetchall()]
            if pl_rows:
                pl_data = _read_json(_playlists_path, {"next_id": 1, "items": []})
                if not pl_data["items"]:
                    next_id = 1
                    for row in pl_rows:
                        new_song_id = old_id_to_new_id.get(row["song_id"], row["song_id"])
                        pl_data["items"].append({
                            "id": next_id,
                            "song_id": new_song_id,
                            "position": row["position"],
                            "label": row.get("label", ""),
                        })
                        next_id += 1
                    pl_data["next_id"] = next_id
                    _write_json(_playlists_path, pl_data)
        except Exception:
            pass

        # ── presentations ─────────────────────────────────────────────────────
        try:
            pres_rows = [_row(r) for r in old.execute("SELECT * FROM presentations").fetchall()]
            if pres_rows:
                pres_data = _read_json(_presentations_path, {"next_id": 1, "items": []})
                if not pres_data["items"]:
                    next_id = 1
                    for row in pres_rows:
                        pres_data["items"].append({
                            "id": next_id,
                            "title": row["title"],
                            "slides": json.loads(row.get("slides", "[]")),
                            "created_at": row.get("created_at", ""),
                            "updated_at": row.get("updated_at", ""),
                        })
                        next_id += 1
                    pres_data["next_id"] = next_id
                    _write_json(_presentations_path, pres_data)
        except Exception:
            pass

        old.close()

        # Rename old DB so we don't migrate again
        os.rename(old_db, old_db + ".migrated")
        return True

    except Exception as e:
        print(f"[Cantio] Migration from cantio.db failed: {e}")
        return False


# ── Settings ──────────────────────────────────────────────────────────────────

def get_settings() -> dict:
    data = _read_json(_settings_path, {})
    result = dict(_SETTINGS_DEFAULTS)
    result.update(data)
    return result


def save_setting(key: str, value):
    s = _read_json(_settings_path, dict(_SETTINGS_DEFAULTS))
    s[key] = str(value)
    _write_json(_settings_path, s)


def save_settings(settings_dict: dict):
    s = _read_json(_settings_path, dict(_SETTINGS_DEFAULTS))
    for k, v in settings_dict.items():
        s[k] = str(v)
    _write_json(_settings_path, s)


# ── Display window configurations ─────────────────────────────────────────────

_DEFAULT_DISPLAY_CONFIGS = [
    {
        "name": "Proiector Principal",
        "screen": 1,
        "fullscreen": True,
        "active": True,
        "settings": {},
    }
]


def get_display_configs() -> list[dict]:
    """Return list of configured display windows from settings.json."""
    data = _read_json(_settings_path, {})
    configs = data.get("display_configs", None)
    if not configs or not isinstance(configs, list):
        return [dict(c) for c in _DEFAULT_DISPLAY_CONFIGS]
    return configs


def save_display_configs(configs: list[dict]):
    """Persist display window configurations to settings.json."""
    data = _read_json(_settings_path, {})
    data["display_configs"] = configs
    _write_json(_settings_path, data)


# ── Window state (cache.json) ─────────────────────────────────────────────────

def get_window_state() -> dict:
    """Return saved UI window/splitter/tab state from cache.json."""
    return get_cache().get("window_state", {})


def save_window_state(state: dict):
    """Persist UI window state to cache.json."""
    c = get_cache()
    c["window_state"] = state
    save_cache(c)


# ── Categories ────────────────────────────────────────────────────────────────

BUILTIN_CATEGORIES = ["All", "General", "Imnuri", "Psalmi", "Colinde", "Laude",
                      "Rugăciuni", "Recunoștință", "Evanghelie", "Copii"]


def get_builtin_categories() -> list[str]:
    """Active builtin category names (excluding 'All'). Persisted in settings."""
    import json
    s = get_settings()
    raw = s.get("builtin_categories", "")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except Exception:
            pass
    return list(BUILTIN_CATEGORIES[1:])


def set_builtin_categories(cats: list[str]) -> None:
    """Persist the user-customized builtin category list."""
    import json
    save_setting("builtin_categories", json.dumps(cats, ensure_ascii=False))


def get_categories() -> list[str]:
    conn = get_songs_db()
    rows = conn.execute(
        "SELECT DISTINCT category FROM songs WHERE category != '' ORDER BY category COLLATE NOCASE"
    ).fetchall()
    conn.close()
    cats = [r["category"] for r in rows]
    return list(dict.fromkeys(["All"] + get_builtin_categories() + cats))


def get_all_categories() -> list[str]:
    """Return all distinct categories from songs (without 'All' prefix)."""
    conn = get_songs_db()
    rows = conn.execute(
        "SELECT DISTINCT category FROM songs"
        " WHERE category IS NOT NULL AND category != ''"
        " ORDER BY category COLLATE NOCASE"
    ).fetchall()
    conn.close()
    return [r["category"] for r in rows]


def get_songs_in_category(category: str) -> list[dict]:
    """Return id + title of all songs in the given category, sorted by title."""
    conn = get_songs_db()
    rows = conn.execute(
        "SELECT id, title FROM songs WHERE category=? ORDER BY title COLLATE NOCASE",
        (category,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_category_counts() -> dict[str, int]:
    """Return {category: song_count} for every non-empty category."""
    conn = get_songs_db()
    rows = conn.execute(
        "SELECT category, COUNT(*) AS cnt FROM songs"
        " WHERE category IS NOT NULL AND category != ''"
        " GROUP BY category ORDER BY category COLLATE NOCASE"
    ).fetchall()
    conn.close()
    return {r["category"]: r["cnt"] for r in rows}


def rename_category(old_name: str, new_name: str) -> int:
    """Rename every song with category=old_name to new_name. Returns rows affected."""
    conn = get_songs_db()
    conn.execute("BEGIN IMMEDIATE")
    c = conn.execute(
        "UPDATE songs SET category=? WHERE category=?", (new_name.strip(), old_name)
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected


def delete_category(name: str, move_to: str = "General") -> int:
    """Move all songs in category name to move_to, then the category ceases to exist."""
    return rename_category(name, move_to or "General")


def move_songs_to_category(song_ids: list[int], new_category: str) -> int:
    """Move a list of songs (by id) to new_category. Returns rows affected."""
    if not song_ids:
        return 0
    conn = get_songs_db()
    conn.execute("BEGIN IMMEDIATE")
    placeholders = ",".join("?" * len(song_ids))
    c = conn.execute(
        f"UPDATE songs SET category=? WHERE id IN ({placeholders})",
        [new_category.strip()] + list(song_ids),
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected


def find_song_by_title(title: str) -> dict | None:
    """Find a song by exact title (case-insensitive). Returns dict or None."""
    conn = get_songs_db()
    row = conn.execute(
        "SELECT id, title FROM songs WHERE title = ? COLLATE NOCASE", (title,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Songs ─────────────────────────────────────────────────────────────────────

def add_song(title, content, slides, author="", category="General",
             language="ro", notes="", formatting=None) -> int:
    conn = None
    try:
        conn = get_songs_db()
        fmt_json = (json.dumps(formatting, ensure_ascii=False)
                    if formatting is not None else None)
        title_norm  = normalize_text(title)
        author_norm = normalize_text(author)
        conn.execute("BEGIN IMMEDIATE")
        c = conn.cursor()
        c.execute(
            "INSERT INTO songs"
            " (title, author, category, language, content, slides, notes, formatting,"
            "  title_normalized, author_normalized)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (title, author, category, language, content,
             json.dumps(slides, ensure_ascii=False), notes, fmt_json,
             title_norm, author_norm)
        )
        song_id = c.lastrowid
        conn.commit()
        return song_id
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def update_song(song_id, title, content, slides, author="", category="General",
                language="ro", notes="", formatting=None):
    conn = None
    try:
        conn = get_songs_db()
        fmt_json = (json.dumps(formatting, ensure_ascii=False)
                    if formatting is not None else None)
        title_norm  = normalize_text(title)
        author_norm = normalize_text(author)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE songs"
            " SET title=?, author=?, category=?, language=?,"
            "     content=?, slides=?, notes=?, formatting=?,"
            "     title_normalized=?, author_normalized=?"
            " WHERE id=?",
            (title, author, category, language, content,
             json.dumps(slides, ensure_ascii=False), notes, fmt_json,
             title_norm, author_norm, song_id)
        )
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def update_song_content(song_id, content, slides) -> bool:
    """Fast update of only content + slides columns — used by the auto-save debounce.
    Avoids re-writing title/author/category/etc on every keystroke."""
    conn = None
    try:
        conn = get_songs_db()
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE songs SET content=?, slides=? WHERE id=?",
            (content, json.dumps(slides, ensure_ascii=False), song_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB] update_song_content: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def delete_song(song_id):
    conn = None
    try:
        conn = get_songs_db()
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM songs WHERE id=?", (song_id,))
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()
    # Also remove from playlist JSON
    pl = _read_json(_playlists_path, {"next_id": 1, "items": []})
    pl["items"] = [it for it in pl["items"] if it["song_id"] != song_id]
    _write_json(_playlists_path, pl)


def get_all_songs(category=None) -> list[dict]:
    conn = get_songs_db()
    if category and category != "All":
        rows = conn.execute(
            "SELECT * FROM songs WHERE category=? ORDER BY title COLLATE NOCASE", (category,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM songs ORDER BY title COLLATE NOCASE"
        ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["slides"] = json.loads(d["slides"])
        d.setdefault("notes", "")
        result.append(d)
    return result


def get_songs_page(page: int = 0, page_size: int = 200,
                   search: str = "", category: str = "") -> list[dict]:
    """Return a page of lightweight song rows (no slides payload)."""
    conn = get_songs_db()
    offset = page * page_size
    cat_filter = category and category != "All"
    if search and cat_filter:
        rows = conn.execute(
            "SELECT id, title, author, category FROM songs"
            " WHERE category=? AND (title LIKE ? OR author LIKE ?)"
            " ORDER BY title COLLATE NOCASE LIMIT ? OFFSET ?",
            (category, f"%{search}%", f"%{search}%", page_size, offset)
        ).fetchall()
    elif search:
        rows = conn.execute(
            "SELECT id, title, author, category FROM songs"
            " WHERE title LIKE ? OR author LIKE ?"
            " ORDER BY title COLLATE NOCASE LIMIT ? OFFSET ?",
            (f"%{search}%", f"%{search}%", page_size, offset)
        ).fetchall()
    elif cat_filter:
        rows = conn.execute(
            "SELECT id, title, author, category FROM songs"
            " WHERE category=? ORDER BY title COLLATE NOCASE LIMIT ? OFFSET ?",
            (category, page_size, offset)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title, author, category FROM songs"
            " ORDER BY title COLLATE NOCASE LIMIT ? OFFSET ?",
            (page_size, offset)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_songs_count(search: str = "", category: str = "") -> int:
    """Return total count of matching songs (for pagination)."""
    conn = get_songs_db()
    cat_filter = category and category != "All"
    if search and cat_filter:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM songs"
            " WHERE category=? AND (title LIKE ? OR author LIKE ?)",
            (category, f"%{search}%", f"%{search}%")
        ).fetchone()["c"]
    elif search:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM songs"
            " WHERE title LIKE ? OR author LIKE ?",
            (f"%{search}%", f"%{search}%")
        ).fetchone()["c"]
    elif cat_filter:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM songs WHERE category=?", (category,)
        ).fetchone()["c"]
    else:
        count = conn.execute("SELECT COUNT(*) AS c FROM songs").fetchone()["c"]
    conn.close()
    return count


def get_song_slides_only(song_id) -> list:
    """Load ONLY the slides column — faster than get_song() for display."""
    conn = get_songs_db()
    row = conn.execute("SELECT slides FROM songs WHERE id=?", (song_id,)).fetchone()
    conn.close()
    if row and row["slides"]:
        try:
            return json.loads(row["slides"])
        except Exception:
            pass
    return []


def _fts5_available() -> bool:
    """Check once whether songs_fts table exists."""
    try:
        conn = get_songs_db()
        conn.execute("SELECT COUNT(*) FROM songs_fts LIMIT 1")
        conn.close()
        return True
    except Exception:
        return False


def search_songs_fast(query: str, limit: int = 200, category: str = "") -> list[dict]:
    """
    FTS5-accelerated search — <10ms on 22k rows.
    Falls back to LIKE (with diacritics normalization) if FTS5 fails or returns nothing.
    Returns lightweight rows (no slides payload).
    """
    if not query or not query.strip():
        return get_songs_titles_only(limit=limit, category=category)

    conn = get_songs_db()
    results: list[dict] = []
    cat_filter = category and category != "All"
    q_orig  = query.strip()
    q_norm  = normalize_text(q_orig)
    q_smart = normalize_search_query(q_orig)   # diacritics + hyphens → spaces
    fts_query       = q_orig.replace('"', '""') + "*"
    fts_query_smart = q_smart.replace('"', '""') + "*" if q_smart != q_orig.lower() else None

    # ── 1. Try FTS5 ───────────────────────────────────────────────────────────
    try:
        if cat_filter:
            rows = conn.execute(
                "SELECT s.id, s.title, s.author, s.category"
                " FROM songs s"
                " JOIN songs_fts ON songs_fts.rowid = s.id"
                " WHERE songs_fts MATCH ? AND s.category = ?"
                " ORDER BY rank LIMIT ?",
                (fts_query, category, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT s.id, s.title, s.author, s.category"
                " FROM songs s"
                " JOIN songs_fts ON songs_fts.rowid = s.id"
                " WHERE songs_fts MATCH ?"
                " ORDER BY rank LIMIT ?",
                (fts_query, limit)
            ).fetchall()
        results = [dict(r) for r in rows]
        # If FTS5 returned nothing with the original query, retry with the
        # normalized form (hyphens→spaces, diacritics→ASCII).
        # This lets "nu L mai" find songs indexed as "nu-L mai".
        if not results and fts_query_smart:
            try:
                if cat_filter:
                    rows = conn.execute(
                        "SELECT s.id, s.title, s.author, s.category"
                        " FROM songs s"
                        " JOIN songs_fts ON songs_fts.rowid = s.id"
                        " WHERE songs_fts MATCH ? AND s.category = ?"
                        " ORDER BY rank LIMIT ?",
                        (fts_query_smart, category, limit)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT s.id, s.title, s.author, s.category"
                        " FROM songs s"
                        " JOIN songs_fts ON songs_fts.rowid = s.id"
                        " WHERE songs_fts MATCH ?"
                        " ORDER BY rank LIMIT ?",
                        (fts_query_smart, limit)
                    ).fetchall()
                results = [dict(r) for r in rows]
            except Exception:
                pass
    except Exception as e_fts:
        print(f"[DB] FTS5 search failed ({e_fts}), falling back to LIKE")
        results = []

    # ── 2. Fallback: LIKE on original, normalized, and smart-normalized forms ──
    # content is searched with an inline SQL REPLACE chain so that hyphens and
    # diacritics inside the stored text are normalized before comparison.
    # This lets "nu L mai" match stored text "nu-L mai" (and vice-versa).
    if not results:
        try:
            like_orig  = f"%{q_orig.lower()}%"
            like_norm  = f"%{q_norm}%"
            like_smart = f"%{q_smart}%"

            # Build a SQL expression that normalises the content column at query time.
            # Applies the same transforms as normalize_search_query():
            #   lowercase → diacritic replacements → hyphens/dashes → spaces
            _content_norm = (
                "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE("
                "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE("
                "LOWER(content),"
                "  'ș','s'),'ş','s'),'ț','t'),'ţ','t'),"
                "  'î','i'),'ă','a'),'â','a'),"
                "  '-',' '),'—',' '),'–',' '),"
                "  '.',' '),',',' '),'!',' ')"
            )

            if cat_filter:
                rows = conn.execute(
                    "SELECT id, title, author, category FROM songs"
                    " WHERE category = ? AND ("
                    "   LOWER(title)           LIKE ? OR"
                    "   title_normalized        LIKE ? OR"
                    "   title_normalized        LIKE ? OR"
                    "   LOWER(author)           LIKE ? OR"
                    "   author_normalized       LIKE ? OR"
                    "   author_normalized       LIKE ? OR"
                    "   content                 LIKE ? OR"
                    f"  {_content_norm}         LIKE ?)"
                    " ORDER BY title COLLATE NOCASE LIMIT ?",
                    (category,
                     like_orig, like_norm, like_smart,
                     like_orig, like_norm, like_smart,
                     like_orig, like_smart, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, title, author, category FROM songs"
                    " WHERE LOWER(title)           LIKE ?"
                    "    OR title_normalized        LIKE ?"
                    "    OR title_normalized        LIKE ?"
                    "    OR LOWER(author)           LIKE ?"
                    "    OR author_normalized       LIKE ?"
                    "    OR author_normalized       LIKE ?"
                    "    OR content                 LIKE ?"
                    f"   OR {_content_norm}         LIKE ?"
                    " ORDER BY title COLLATE NOCASE LIMIT ?",
                    (like_orig, like_norm, like_smart,
                     like_orig, like_norm, like_smart,
                     like_orig, like_smart, limit)
                ).fetchall()
            results = [dict(r) for r in rows]
        except Exception as e_like:
            print(f"[DB] LIKE fallback failed: {e_like}")
            results = []

    conn.close()
    _log.debug("Search '%s' → %d results", q_orig, len(results))
    print(f"[DB] Search '{q_orig}' → {len(results)} results")
    return results


def get_songs_titles_only(limit: int = 200, offset: int = 0,
                          search: str = "", category: str = "") -> list[dict]:
    """
    Load ONLY id, title, author, category — no slides, no content.
    Uses FTS5 when searching, index scan when browsing.
    """
    if search.strip():
        return search_songs_fast(search, limit=limit, category=category)
    conn = get_songs_db()
    cat_filter = category and category != "All"
    if cat_filter:
        rows = conn.execute(
            "SELECT id, title, author, category FROM songs"
            " WHERE category=? ORDER BY title COLLATE NOCASE LIMIT ? OFFSET ?",
            (category, limit, offset)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title, author, category FROM songs"
            " ORDER BY title COLLATE NOCASE LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_songs(query, category=None) -> list[dict]:
    conn = get_songs_db()
    if category and category != "All":
        rows = conn.execute(
            "SELECT * FROM songs WHERE category=? AND (title LIKE ? OR content LIKE ?)"
            " ORDER BY title COLLATE NOCASE",
            (category, f"%{query}%", f"%{query}%")
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM songs WHERE title LIKE ? OR content LIKE ?"
            " ORDER BY title COLLATE NOCASE",
            (f"%{query}%", f"%{query}%")
        ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["slides"] = json.loads(d["slides"])
        d.setdefault("notes", "")
        result.append(d)
    return result


def get_song(song_id) -> dict | None:
    conn = get_songs_db()
    row = conn.execute("SELECT * FROM songs WHERE id=?", (song_id,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["slides"] = json.loads(d["slides"])
        d.setdefault("notes", "")
        fmt_raw = d.get("formatting")
        d["formatting"] = json.loads(fmt_raw) if fmt_raw else None
        trans_raw = d.get("translations")
        d["translations"] = json.loads(trans_raw) if trans_raw else {}
        return d
    return None


def get_song_translations(song_id) -> dict:
    conn = get_songs_db()
    row = conn.execute(
        "SELECT translations FROM songs WHERE id=?", (song_id,)
    ).fetchone()
    conn.close()
    if row and row["translations"]:
        try:
            return json.loads(row["translations"])
        except Exception:
            pass
    return {}


def save_song_translation(song_id, lang_code: str, translated_text: str):
    translations = get_song_translations(song_id)
    translations[lang_code] = translated_text
    conn = None
    try:
        conn = get_songs_db()
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE songs SET translations=? WHERE id=?",
            (json.dumps(translations, ensure_ascii=False), song_id)
        )
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


# ── Playlist (playlists.json) ─────────────────────────────────────────────────

def _read_playlists() -> dict:
    return _read_json(_playlists_path, {"next_id": 1, "items": []})


def get_playlist() -> list[dict]:
    pl = _read_playlists()
    result = []
    for item in sorted(pl["items"], key=lambda x: x["position"]):
        song = get_song(item["song_id"])
        if song:
            result.append({
                "id": item["id"],
                "song_id": item["song_id"],
                "position": item["position"],
                "label": item.get("label", ""),
                "title": song["title"],
                "slides": song["slides"],
                "notes": song.get("notes", ""),
            })
    return result


def add_to_playlist(song_id, label=""):
    pl = _read_playlists()
    next_id = pl.get("next_id", 1)
    pos = max((it["position"] for it in pl["items"]), default=0) + 1
    pl["items"].append({"id": next_id, "song_id": song_id, "position": pos, "label": label})
    pl["next_id"] = next_id + 1
    _write_json(_playlists_path, pl)


def remove_from_playlist(playlist_id):
    pl = _read_playlists()
    pl["items"] = [it for it in pl["items"] if it["id"] != playlist_id]
    _write_json(_playlists_path, pl)


def clear_playlist():
    _write_json(_playlists_path, {"next_id": 1, "items": []})


def reorder_playlist(ordered_ids):
    pl = _read_playlists()
    id_map = {it["id"]: it for it in pl["items"]}
    for pos, pid in enumerate(ordered_ids, 1):
        if pid in id_map:
            id_map[pid]["position"] = pos
    pl["items"] = list(id_map.values())
    _write_json(_playlists_path, pl)


# New explicit helpers
def get_playlists() -> list[dict]:
    return get_playlist()


def save_playlists(items: list[dict]):
    pl = _read_playlists()
    pl["items"] = items
    _write_json(_playlists_path, pl)


# ── Bible (bible.db) ──────────────────────────────────────────────────────────

def get_bible_books() -> list[dict]:
    conn = get_bible_db()
    rows = conn.execute("SELECT * FROM bible_books ORDER BY book_order").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_chapters(book_id) -> list[int]:
    conn = get_bible_db()
    rows = conn.execute(
        "SELECT DISTINCT chapter FROM bible_verses WHERE book_id=? ORDER BY chapter", (book_id,)
    ).fetchall()
    conn.close()
    return [r["chapter"] for r in rows]


def get_verses(book_id, chapter) -> list[dict]:
    conn = get_bible_db()
    rows = conn.execute(
        "SELECT * FROM bible_verses WHERE book_id=? AND chapter=? ORDER BY verse",
        (book_id, chapter)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_verse(book_id, chapter, verse_num) -> dict | None:
    conn = get_bible_db()
    row = conn.execute(
        "SELECT * FROM bible_verses WHERE book_id=? AND chapter=? AND verse=?",
        (book_id, chapter, verse_num)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def search_bible_text(query, limit=80) -> list[dict]:
    conn = get_bible_db()
    rows = conn.execute(
        """SELECT bv.*, bb.name as book_name
           FROM bible_verses bv
           JOIN bible_books bb ON bv.book_id = bb.id
           WHERE bv.text LIKE ?
           ORDER BY bb.book_order, bv.chapter, bv.verse
           LIMIT ?""",
        (f"%{query}%", limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def import_bible_data(books, verses):
    conn = None
    try:
        conn = get_bible_db()
        conn.execute("BEGIN IMMEDIATE")
        c = conn.cursor()
        c.execute("DELETE FROM bible_verses")
        c.execute("DELETE FROM bible_books")
        for b in books:
            c.execute(
                "INSERT INTO bible_books (id, name, abbreviation, testament, book_order)"
                " VALUES (?,?,?,?,?)",
                (b["id"], b["name"], b["abbreviation"], b["testament"], b["book_order"])
            )
        for v in verses:
            c.execute(
                "INSERT INTO bible_verses (book_id, chapter, verse, text, translation)"
                " VALUES (?,?,?,?,?)",
                (v["book_id"], v["chapter"], v["verse"], v["text"], v.get("translation", "VBA"))
            )
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def has_bible() -> bool:
    conn = get_bible_db()
    count = conn.execute("SELECT COUNT(*) as c FROM bible_books").fetchone()["c"]
    conn.close()
    return count > 0


# ── Stage layouts (stage.json) ────────────────────────────────────────────────

def get_stage_layouts() -> dict:
    return _read_json(_stage_path, {})


def save_stage_layout(name: str, layout_data):
    data = get_stage_layouts()
    data[name] = layout_data
    _write_json(_stage_path, data)


# ── Cache (cache.json) ────────────────────────────────────────────────────────

def get_cache() -> dict:
    return _read_json(_cache_path, {"recent_files": []})


def save_cache(data: dict):
    _write_json(_cache_path, data)


def get_recent_files() -> list[str]:
    return get_cache().get("recent_files", [])


def add_recent_file(path: str):
    c = get_cache()
    files = c.get("recent_files", [])
    if path in files:
        files.remove(path)
    files.insert(0, path)
    c["recent_files"] = files[:20]
    save_cache(c)


# ── Presentations (presentations.json) ────────────────────────────────────────

def _read_presentations() -> dict:
    return _read_json(_presentations_path, {"next_id": 1, "items": []})


def add_presentation(title, slides=None) -> int:
    data = _read_presentations()
    next_id = data.get("next_id", 1)
    now = datetime.now().isoformat(timespec="seconds")
    data["items"].append({
        "id": next_id,
        "title": title,
        "slides": slides or [],
        "created_at": now,
        "updated_at": now,
    })
    data["next_id"] = next_id + 1
    _write_json(_presentations_path, data)
    return next_id


def update_presentation(pres_id, title, slides):
    data = _read_presentations()
    now = datetime.now().isoformat(timespec="seconds")
    for item in data["items"]:
        if item["id"] == pres_id:
            item["title"] = title
            item["slides"] = slides
            item["updated_at"] = now
            break
    _write_json(_presentations_path, data)


def delete_presentation(pres_id):
    data = _read_presentations()
    data["items"] = [it for it in data["items"] if it["id"] != pres_id]
    _write_json(_presentations_path, data)


def get_all_presentations() -> list[dict]:
    data = _read_presentations()
    return sorted(data["items"], key=lambda x: x.get("updated_at", ""), reverse=True)


def get_presentation(pres_id) -> dict | None:
    data = _read_presentations()
    for item in data["items"]:
        if item["id"] == pres_id:
            return dict(item)
    return None


# ── Slide Labels ─────────────────────────────────────────────────────────────

LABEL_COLORS = {
    "Strofa":      "#cba6f7",   # violet
    "Verse":       "#cba6f7",   # violet
    "Refren":      "#a6e3a1",   # verde
    "Chorus":      "#a6e3a1",   # verde
    "Cor":         "#89dceb",   # cyan
    "Bridge":      "#f9e2af",   # galben
    "Pre-Refren":  "#fab387",   # portocaliu
    "Pod":         "#fab387",   # portocaliu
    "Intro":       "#89b4fa",   # albastru
    "Outro":       "#89b4fa",   # albastru
    "Final":       "#f38ba8",   # roșu
}


def get_label_color(label: str) -> str:
    """Return hex color for a given label string, or grey as default."""
    for key, color in LABEL_COLORS.items():
        if key.lower() in label.lower():
            return color
    return "#6c7086"


def detect_label(text: str, index: int) -> str:
    """Auto-detect section label from first line of a slide."""
    import re as _re
    first_line = text.split("\n")[0].strip() if text else ""
    patterns = [
        (_re.compile(r"^R[ef]*\s*[:.]\s*", _re.I),          "Refren"),
        (_re.compile(r"^Refren\b",          _re.I),          "Refren"),
        (_re.compile(r"^Chorus\b",          _re.I),          "Chorus"),
        (_re.compile(r"^C\s*[:.]\s*",       _re.I),          "Cor"),
        (_re.compile(r"^Cor\b",             _re.I),          "Cor"),
        (_re.compile(r"^Bridge\b",          _re.I),          "Bridge"),
        (_re.compile(r"^Pre-?refren\b",     _re.I),          "Pre-Refren"),
        (_re.compile(r"^Intro\b",           _re.I),          "Intro"),
        (_re.compile(r"^Outro\b",           _re.I),          "Outro"),
        (_re.compile(r"^Pod\s*[:.]\s*",     _re.I),          "Pod"),
        (_re.compile(r"^Final\b",           _re.I),          "Final"),
        (_re.compile(r"^(\d+)\s*[.)]\s*"),                   None),   # "1." → Strofa 1
        (_re.compile(r"^Strofa\s+(\d+)",    _re.I),          None),   # "Strofa 2"
        (_re.compile(r"^Verse\s*(\d*)",     _re.I),          None),   # "Verse 1"
    ]
    for pat, label in patterns:
        m = pat.match(first_line)
        if m:
            if label is not None:
                return label
            # Numbered: extract digit
            num = m.group(1) if m.lastindex else str(index + 1)
            if "Verse" in (pat.pattern or ""):
                return f"Verse {num}".strip()
            return f"Strofa {num}"
    return f"Strofa {index + 1}"


def migrate_slides_format(slides) -> list[dict]:
    """Convert slides list[str] → list[dict] with label metadata.
    Already-dict slides are passed through unchanged."""
    if not slides:
        return []
    result = []
    for i, s in enumerate(slides):
        if isinstance(s, str):
            label = detect_label(s, i)
            result.append({
                "text":        s,
                "label":       label,
                "label_color": get_label_color(label),
            })
        elif isinstance(s, dict):
            # Ensure label fields exist
            if "label" not in s:
                s["label"] = detect_label(s.get("text", ""), i)
            if "label_color" not in s:
                s["label_color"] = get_label_color(s["label"])
            result.append(s)
    return result


# ── Uppercase Songs ───────────────────────────────────────────────────────────

def uppercase_songs(song_ids=None, category=None) -> int:
    """Convert ALL letters in title and lyrics to UPPERCASE.
    scope: song_ids (list[int]) > category (str) > all songs.
    Returns number of updated songs."""
    conn = get_songs_db()
    try:
        if song_ids:
            placeholders = ",".join("?" * len(song_ids))
            rows = conn.execute(
                f"SELECT id, title, content, slides, author FROM songs"
                f" WHERE id IN ({placeholders})",
                song_ids,
            ).fetchall()
        elif category:
            rows = conn.execute(
                "SELECT id, title, content, slides, author FROM songs WHERE category=?",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, content, slides, author FROM songs"
            ).fetchall()

        updated = 0
        for row in rows:
            d = dict(row)
            new_content = d["content"].upper() if d["content"] else ""
            raw_slides  = json.loads(d["slides"]) if d["slides"] else []
            new_slides  = [
                s.upper() if isinstance(s, str) else
                {**s, "text": s.get("text", "").upper()}
                for s in raw_slides
            ]
            conn.execute(
                "UPDATE songs SET content=?, slides=? WHERE id=?",
                (new_content, json.dumps(new_slides, ensure_ascii=False), d["id"]),
            )
            updated += 1
        conn.commit()
        return updated
    finally:
        conn.close()


# ── Split Slides by Line Count ────────────────────────────────────────────────

def split_songs_by_lines(lines_per_slide: int,
                         song_ids=None, category=None) -> int:
    """Re-slice all slides so each slide has at most `lines_per_slide` lines.
    scope: song_ids > category > all songs.
    Returns number of updated songs."""
    conn = get_songs_db()
    try:
        if song_ids:
            placeholders = ",".join("?" * len(song_ids))
            rows = conn.execute(
                f"SELECT id, content FROM songs WHERE id IN ({placeholders})",
                song_ids,
            ).fetchall()
        elif category:
            rows = conn.execute(
                "SELECT id, content FROM songs WHERE category=?", (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT id, content FROM songs").fetchall()

        updated = 0
        for row in rows:
            d = dict(row)
            content = d["content"] or ""
            all_lines = [l for l in content.splitlines() if l.strip()]
            if not all_lines:
                continue
            new_slides = [
                "\n".join(all_lines[i:i + lines_per_slide])
                for i in range(0, len(all_lines), lines_per_slide)
                if all_lines[i:i + lines_per_slide]
            ]
            new_content = "\n\n".join(new_slides)
            conn.execute(
                "UPDATE songs SET content=?, slides=? WHERE id=?",
                (new_content, json.dumps(new_slides, ensure_ascii=False), d["id"]),
            )
            updated += 1
        conn.commit()
        return updated
    finally:
        conn.close()


# ── Export / Import JSON ──────────────────────────────────────────────────────

def export_db_json(path):
    songs_conn = get_songs_db()
    songs = [dict(r) for r in songs_conn.execute("SELECT * FROM songs").fetchall()]
    songs_conn.close()
    for s in songs:
        s["slides"] = json.loads(s["slides"])

    bible_conn = get_bible_db()
    books = [dict(r) for r in bible_conn.execute("SELECT * FROM bible_books").fetchall()]
    verses = [dict(r) for r in bible_conn.execute(
        "SELECT * FROM bible_verses LIMIT 100000"
    ).fetchall()]
    bible_conn.close()

    settings = get_settings()
    pl = _read_playlists()
    playlist = pl.get("items", [])

    data = {
        "version": 3,
        "songs": songs,
        "bible_books": books,
        "bible_verses": verses,
        "settings": settings,
        "playlist": playlist,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return len(songs)


def import_db_json(path, merge=True) -> int:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    conn = get_songs_db()
    c = conn.cursor()
    imported_songs = 0

    for s in data.get("songs", []):
        slides = s.get("slides", [])
        if isinstance(slides, str):
            slides = json.loads(slides)
        if merge:
            existing = conn.execute(
                "SELECT id FROM songs WHERE title=?", (s["title"],)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE songs SET content=?, slides=?, author=?, category=?,"
                    " language=?, notes=? WHERE id=?",
                    (s.get("content", ""), json.dumps(slides, ensure_ascii=False),
                     s.get("author", ""), s.get("category", "General"),
                     s.get("language", "ro"), s.get("notes", ""), existing["id"])
                )
            else:
                c.execute(
                    "INSERT INTO songs (title, author, category, language, content, slides, notes)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (s.get("title", "Untitled"), s.get("author", ""),
                     s.get("category", "General"), s.get("language", "ro"),
                     s.get("content", ""), json.dumps(slides, ensure_ascii=False),
                     s.get("notes", ""))
                )
                imported_songs += 1
        else:
            c.execute(
                "INSERT OR IGNORE INTO songs (title, author, category, language, content, slides, notes)"
                " VALUES (?,?,?,?,?,?,?)",
                (s.get("title", "Untitled"), s.get("author", ""),
                 s.get("category", "General"), s.get("language", "ro"),
                 s.get("content", ""), json.dumps(slides, ensure_ascii=False),
                 s.get("notes", ""))
            )
            imported_songs += 1

    conn.commit()
    conn.close()
    return imported_songs


# ── PDF Export ────────────────────────────────────────────────────────────────

def export_playlist_pdf(path):
    """Export current playlist to PDF using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas as rl_canvas
    except ImportError:
        raise ImportError("reportlab is not installed. Run: pip install reportlab")

    items = get_playlist()
    c = rl_canvas.Canvas(path, pagesize=A4)
    w, h = A4

    c.setFont("Helvetica-Bold", 20)
    c.setFillColorRGB(0.3, 0.6, 0.9)
    c.drawString(2 * cm, h - 2 * cm, "Cantio — Service Order")

    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(2 * cm, h - 2.8 * cm,
                 f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                 f"  |  {len(items)} items")

    y = h - 4 * cm
    for i, item in enumerate(items, 1):
        if y < 3 * cm:
            c.showPage()
            y = h - 2 * cm

        c.setFillColorRGB(0.2, 0.4, 0.7)
        c.roundRect(2 * cm, y - 0.4 * cm, 0.7 * cm, 0.6 * cm, 0.1 * cm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(2.35 * cm, y - 0.2 * cm, str(i))

        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(3 * cm, y - 0.1 * cm, item.get("title", "Untitled")[:60])

        slides = item.get("slides", [])
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawString(3 * cm, y - 0.45 * cm,
                     f"{len(slides)} slide{'s' if len(slides) != 1 else ''}")

        c.setStrokeColorRGB(0.2, 0.2, 0.2)
        c.line(2 * cm, y - 0.65 * cm, w - 2 * cm, y - 0.65 * cm)
        y -= 1.2 * cm

    c.save()
    return len(items)
