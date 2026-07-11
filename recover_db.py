#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
recover_db.py — Unealtă de recuperare pentru baza de date Cantio (songs.db).

De folosit când Cantio dă eroarea "database disk image is malformed" sau crapă
la editarea/salvarea cântărilor.

Ce face, în ordine (de la cel mai blând la cel mai agresiv):
  1. Face BACKUP la baza actuală (nu se atinge de original fără copie).
  2. Verifică integritatea (PRAGMA integrity_check).
  3. Dacă doar indexul de căutare FTS5 e corupt → îl RECONSTRUIEȘTE
     (cazul cel mai frecvent — zero pierderi, cântările rămân neatinse).
  4. Dacă baza în sine e coruptă → SALVEAZĂ cântare-cu-cântare tot ce se poate
     citi într-o bază NOUĂ curată, sărind peste rândurile stricate.

Rulare:
    python recover_db.py                 # auto-detectează profilurile din ~/Cantio
    python recover_db.py "cale/songs.db" # o bază anume

NU șterge nimic. Originalul rămâne; recuperarea se scrie în songs.db.recovered
și abia la final, cu confirmarea ta, înlocuiește songs.db.
"""

import os
import sys
import shutil
import sqlite3
import datetime


def _p(msg=""):
    """print tolerant la console-uri fără UTF-8 (Windows cp1250)."""
    try:
        print(msg)
    except Exception:
        print(str(msg).encode("ascii", "ignore").decode("ascii"))


def find_song_dbs():
    """Găsește toate songs.db din ~/Cantio/profiles/*/."""
    home = os.path.expanduser("~")
    root = os.path.join(home, "Cantio", "profiles")
    found = []
    if os.path.isdir(root):
        for prof in sorted(os.listdir(root)):
            db = os.path.join(root, prof, "songs.db")
            if os.path.isfile(db):
                found.append(db)
    return found


def backup(db_path):
    """Copie de siguranță cu timestamp. Copiază și -wal/-shm dacă există."""
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bkp = f"{db_path}.backup_{stamp}"
    shutil.copy2(db_path, bkp)
    for ext in ("-wal", "-shm"):
        side = db_path + ext
        if os.path.exists(side):
            shutil.copy2(side, bkp + ext)
    return bkp


def integrity(db_path):
    """Rulează integrity_check. Întoarce (ok: bool, mesaje: list[str])."""
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute("PRAGMA integrity_check").fetchall()
        conn.close()
        msgs = [r[0] for r in rows]
        return (msgs == ["ok"], msgs)
    except sqlite3.DatabaseError as e:
        return (False, [f"integrity_check a eșuat: {e}"])


def try_fts_rebuild(db_path):
    """
    Încearcă să reconstruiască DOAR indexul FTS5. Cazul fericit: datele sunt
    bune, doar căutarea era stricată. Întoarce True dacă a reușit.
    """
    try:
        conn = sqlite3.connect(db_path, timeout=30)
        # Numărăm cântările — dacă asta merge, tabelul principal e citibil.
        n = conn.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
        _p(f"   • Tabelul 'songs' e citibil: {n} cântări găsite.")
        # Reconstruiește indexul FTS din tabelul de conținut.
        conn.execute("INSERT INTO songs_fts(songs_fts) VALUES('rebuild')")
        conn.commit()
        # Test: o căutare simplă nu mai trebuie să crape.
        conn.execute("SELECT rowid FROM songs_fts LIMIT 1").fetchall()
        conn.close()
        _p("   ✅ Index de căutare (FTS5) reconstruit cu succes.")
        return True
    except sqlite3.DatabaseError as e:
        _p(f"   ⚠ Reconstruirea FTS nu a mers ({e}). Trec la salvare completă.")
        try:
            conn.close()
        except Exception:
            pass
        return False


SONGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT DEFAULT '',
    category TEXT DEFAULT 'General',
    language TEXT DEFAULT 'ro',
    content TEXT NOT NULL,
    slides TEXT NOT NULL,
    notes TEXT DEFAULT '',
    formatting TEXT DEFAULT NULL,
    translations TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def salvage(db_path):
    """
    Salvează rând-cu-rând tot ce se poate citi din 'songs' într-o bază nouă.
    Sare peste rândurile corupte. Întoarce (nou_db, recuperate, sarite).
    """
    new_db = db_path + ".recovered"
    if os.path.exists(new_db):
        os.remove(new_db)

    src = sqlite3.connect(db_path, timeout=30)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(new_db)
    dst.execute("PRAGMA journal_mode=WAL")
    dst.execute(SONGS_SCHEMA)

    # Ce coloane există de fapt în baza veche?
    try:
        cols = [r[1] for r in src.execute("PRAGMA table_info(songs)").fetchall()]
    except sqlite3.DatabaseError:
        cols = ["id", "title", "content", "slides"]
    want = [c for c in ("id", "title", "author", "category", "language",
                        "content", "slides", "notes", "formatting",
                        "translations", "created_at") if c in cols]

    # Aflăm intervalul de id-uri ca să iterăm rând cu rând (rezistent la corupție).
    try:
        max_id = src.execute("SELECT MAX(id) FROM songs").fetchone()[0] or 0
    except sqlite3.DatabaseError:
        max_id = 0

    recovered, skipped = 0, 0
    placeholders = ",".join("?" for _ in want)
    collist = ",".join(want)

    def _insert(row):
        vals = [row[c] for c in want]
        dst.execute(f"INSERT INTO songs({collist}) VALUES({placeholders})", vals)

    if max_id > 0:
        # Iterăm id cu id: o cântare coruptă nu strică tot batch-ul.
        for i in range(1, max_id + 1):
            try:
                row = src.execute(
                    f"SELECT {collist} FROM songs WHERE id=?", (i,)
                ).fetchone()
                if row is None:
                    continue
                if not row["title"] or row["slides"] is None:
                    skipped += 1
                    continue
                _insert(row)
                recovered += 1
            except sqlite3.DatabaseError:
                skipped += 1
            if recovered % 200 == 0 and recovered:
                dst.commit()
    else:
        # Fără id-uri: încercăm un singur SELECT tolerant.
        try:
            for row in src.execute(f"SELECT {collist} FROM songs"):
                try:
                    _insert(row)
                    recovered += 1
                except sqlite3.DatabaseError:
                    skipped += 1
        except sqlite3.DatabaseError:
            pass

    dst.commit()
    # Reconstruiește indexul FTS pe baza nouă (curată).
    try:
        dst.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS songs_fts USING fts5(
                title, author, content='songs', content_rowid='id',
                tokenize='unicode61 remove_diacritics 2')
        """)
        dst.execute("INSERT INTO songs_fts(rowid, title, author) "
                    "SELECT id, title, author FROM songs")
        dst.commit()
    except sqlite3.DatabaseError:
        pass

    src.close()
    dst.close()
    return new_db, recovered, skipped


def recover_one(db_path):
    _p("=" * 64)
    _p(f"Bază: {db_path}")
    size_mb = os.path.getsize(db_path) / 1048576
    _p(f"Mărime: {size_mb:.1f} MB")

    _p("\n[1/4] Fac backup...")
    bkp = backup(db_path)
    _p(f"   ✅ Backup: {bkp}")

    _p("\n[2/4] Verific integritatea...")
    ok, msgs = integrity(db_path)
    if ok:
        _p("   ✅ Baza pare INTACTĂ (integrity_check = ok).")
        _p("   Încerc totuși să reconstruiesc indexul de căutare, pentru siguranță.")
        try_fts_rebuild(db_path)
        _p("\n✅ GATA. Deschide Cantio și testează.")
        return
    else:
        _p("   ⚠ Probleme de integritate:")
        for m in msgs[:6]:
            _p(f"      - {m}")

    _p("\n[3/4] Încerc reparare BLÂNDĂ (doar indexul de căutare FTS5)...")
    if try_fts_rebuild(db_path):
        ok2, _ = integrity(db_path)
        if ok2:
            _p("\n✅ GATA — reparat fără pierderi! Deschide Cantio și testează.")
            return
        _p("   (Index reconstruit, dar baza tot are probleme — trec la salvare.)")

    _p("\n[4/4] Salvez cântările într-o bază NOUĂ curată...")
    new_db, rec, skip = salvage(db_path)
    _p(f"   ✅ Recuperate: {rec} cântări   |   sărite (corupte): {skip}")
    _p(f"   Bază nouă: {new_db}")

    _p("\nVrei să înlocuiesc baza coruptă cu cea recuperată?")
    _p("(originalul rămâne salvat în backup-ul de mai sus)")
    ans = input("Înlocuiesc songs.db cu versiunea recuperată? [da/nu]: ").strip().lower()
    if ans in ("da", "d", "yes", "y"):
        for ext in ("", "-wal", "-shm"):
            side = db_path + ext
            if os.path.exists(side):
                os.remove(side)
        shutil.move(new_db, db_path)
        _p("   ✅ Înlocuit. Deschide Cantio — ar trebui să meargă.")
    else:
        _p(f"   Am lăsat totul așa. Baza recuperată e la: {new_db}")
        _p("   O poți inspecta și redenumi manual în 'songs.db' când ești sigur.")


def main():
    _p("╔══════════════════════════════════════════════════════════════╗")
    _p("║   Cantio — Recuperare bază de date (songs.db)                 ║")
    _p("╚══════════════════════════════════════════════════════════════╝")

    if len(sys.argv) > 1:
        targets = [sys.argv[1]]
    else:
        targets = find_song_dbs()
        if not targets:
            _p("\nNu am găsit niciun songs.db în ~/Cantio/profiles/.")
            _p("Rulează cu calea explicită: python recover_db.py \"cale\\songs.db\"")
            return
        _p(f"\nAm găsit {len(targets)} bază/baze de date:")
        for i, t in enumerate(targets, 1):
            _p(f"  {i}. {t}")

    for t in targets:
        if not os.path.isfile(t):
            _p(f"\n⚠ Nu există: {t}")
            continue
        try:
            recover_one(t)
        except Exception as e:
            _p(f"\n❌ Eroare la {t}: {e}")
            _p("   Backup-ul e în siguranță. Trimite-mi mesajul ăsta.")

    _p("\n" + "=" * 64)
    _p("Gata. Dacă tot nu merge, trimite-mi textul complet de mai sus.")


if __name__ == "__main__":
    main()
