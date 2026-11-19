"""
Cantio - Importer
Supports: TXT, DOCX, PDF, VideoPsalm (.json/.xml/.vpc), EasyWorship (.ewsx/.db)
(Importul de biblii din fișiere a fost eliminat.)
"""
import os
import re
import json
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


# ── Curățare text importat (VideoPsalm etc.) ──────────────────────────────────
# Marcaje VideoPsalm care nu trebuie afișate: <s1076>, </s>, <sb>, <chorus> etc.
_VP_TAG_RE = re.compile(r"</?\s*(?:s\d*|sb|chorus|verse|bridge|tag|c\d*)\s*>",
                        re.IGNORECASE)
# Numere de verset de tip "<1076>" sau coduri izolate.
_VP_NUMTAG_RE = re.compile(r"<\s*\d+\s*>")


def clean_imported_lyrics(text: str) -> str:
    """Șterge marcajele reziduale din import (VideoPsalm etc.) — ex. <s1076>,
    </s>, <sb>. NU atinge marcajele de repetare bisericesc /: … :/ și nici
    etichetele R:/C:/B:. Returnează textul curat (sau cel original dacă nu e str)."""
    if not isinstance(text, str) or not text:
        return text
    _s = text.lstrip()
    if _s.startswith("<!DOCTYPE") or _s.startswith("<html"):
        return text   # document HTML rich (din editor) — nu are marcaje VideoPsalm
    cleaned = _VP_TAG_RE.sub("", text)
    cleaned = _VP_NUMTAG_RE.sub("", cleaned)
    # curăță spațiile goale rămase la capete de linie
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned


def has_import_artifacts(text: str) -> bool:
    """Adevărat dacă textul conține marcaje reziduale de import (de curățat)."""
    if not isinstance(text, str) or not text:
        return False
    return bool(_VP_TAG_RE.search(text) or _VP_NUMTAG_RE.search(text))


# ── Encoding detection ────────────────────────────────────────────────────────

def detect_encoding(filepath):
    """Try a sequence of encodings and return the first one that reads successfully."""
    with open(filepath, "rb") as f:
        raw_start = f.read(4)

    # BOM sniffing
    if raw_start[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if raw_start[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    if raw_start[:4] in (b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00"):
        return "utf-32"

    for enc in ["utf-8", "utf-8-sig", "cp1250", "cp1252", "iso-8859-2", "latin-1"]:
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.read(2000)
            if content and len(content) > 10:
                return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "latin-1"


def _try_parse_xml_with_encodings(filepath_or_bytes):
    """
    Parse XML from a filepath or raw bytes, trying multiple encodings.
    Returns the root Element or None.
    """
    if isinstance(filepath_or_bytes, (str, Path)):
        # Standard parse first — handles UTF-8, UTF-16 with BOM, and <?xml ...?> declarations
        try:
            return ET.parse(str(filepath_or_bytes)).getroot()
        except ET.ParseError:
            pass
        with open(filepath_or_bytes, "rb") as f:
            raw = f.read()
    else:
        raw = filepath_or_bytes
        try:
            return ET.fromstring(raw)
        except ET.ParseError:
            pass

    for enc in ["utf-16", "utf-16-le", "utf-16-be", "utf-8-sig",
                "utf-8", "cp1250", "cp1252", "iso-8859-2", "latin-1"]:
        try:
            text = raw.decode(enc)
            text = text.lstrip("\ufeff")  # strip BOM
            # Ensure there's an XML declaration
            if not text.strip().startswith("<?xml"):
                text = '<?xml version="1.0" encoding="utf-8"?>' + text
            root = ET.fromstring(text.encode("utf-8"))
            print(f"[XML] Parsed with encoding: {enc}")
            return root
        except Exception:
            continue
    return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def text_to_slides(text):
    """Split text into slides by double newline (strophes)."""
    if not text or not str(text).strip():
        return []
    blocks = [b.strip() for b in str(text).strip().split("\n\n") if b.strip()]
    return blocks if blocks else [str(text).strip()]


def strip_rtf(text):
    """
    Extract plain text from an RTF-encoded string.
    Handles: metadata groups (fonttbl/colortbl/…), \\uN unicode, \\'xx hex, \\par breaks.
    """
    if not isinstance(text, str):
        text = str(text)
    text = text.strip()
    if not text.startswith("{\\rtf"):
        return text

    # 0. Remove known non-text metadata groups using a simple pass
    #    We iterate because groups may be nested one level deep
    _JUNK = ("fonttbl", "colortbl", "stylesheet", "info",
              "pict", "object", "filetbl", "listtable", "mmathPr")
    # Pattern that handles one level of nested braces inside the group
    _inner = r"[^{}]*(?:\{[^{}]*\}[^{}]*)*"
    for _ in range(3):  # a few passes handles shallow nesting
        for grp in _JUNK:
            text = re.sub(r"\{\\" + grp + _inner + r"\}", "", text)
            text = re.sub(r"\{\\[*]\s*\\" + grp + _inner + r"\}", "", text)

    # 1. RTF Unicode escapes: \uN? (N is signed decimal codepoint, ? is fallback char)
    def rtf_uni(m):
        try:
            n = int(m.group(1))
            if n < 0:
                n += 65536
            return chr(n)
        except Exception:
            return ""
    # Consume \uN plus its one-character ANSI fallback (may be \'xx or a plain char)
    text = re.sub(r"\\u(-?\d+)\s?(?:\\'[0-9a-fA-F]{2}|[^\\\s{}])?", rtf_uni, text)

    # 2. Hex-escaped characters (cp1252 default code page)
    def unhex(m):
        try:
            return bytes.fromhex(m.group(1)).decode("cp1252", errors="replace")
        except Exception:
            return ""
    text = re.sub(r"\\'([0-9a-fA-F]{2})", unhex, text)

    # 3. Paragraph / line breaks — BEFORE control-word removal
    text = re.sub(r"\\pard?\b[^a-zA-Z]?", "\n", text)
    text = re.sub(r"\\par\b\s?", "\n", text)
    text = re.sub(r"\\line\b\s?", "\n", text)
    text = re.sub(r"\\tab\b\s?", "\t", text)

    # 4. Remove remaining RTF control words (\word, \word123, \word-123)
    text = re.sub(r"\\[a-zA-Z]+\-?\d*\s?", "", text)

    # 5. Remove brace markers (structural, not content in RTF)
    text = re.sub(r"[{}\\]", "", text)

    # 6. Tidy whitespace
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _has_garbage(text, threshold=0.15):
    """Return True if more than threshold fraction of chars look like encoding garbage."""
    if not text:
        return False
    garbage = sum(1 for c in text if ord(c) > 0xFFFD or c in "\x00\x01\x02\x03\x04\x05")
    return (garbage / len(text)) > threshold


# ── TXT ───────────────────────────────────────────────────────────────────────

def import_txt(filepath):
    enc = detect_encoding(filepath)
    with open(filepath, "r", encoding=enc, errors="replace") as f:
        content = f.read()
    title = Path(filepath).stem
    slides = text_to_slides(content)
    return [{"title": title, "content": content, "slides": slides, "language": "ro"}]


# ── DOCX ──────────────────────────────────────────────────────────────────────

def import_docx(filepath):
    try:
        import docx
        doc = docx.Document(filepath)
        content = "\n".join(p.text for p in doc.paragraphs)
        title = Path(filepath).stem
        slides = text_to_slides(content)
        return [{"title": title, "content": content, "slides": slides, "language": "ro"}]
    except Exception as e:
        raise ImportError(f"DOCX import failed: {e}")


# ── PDF ───────────────────────────────────────────────────────────────────────

def import_pdf(filepath):
    try:
        import fitz
        doc = fitz.open(filepath)
        content = "\n\n".join(page.get_text() for page in doc)
        doc.close()
        title = Path(filepath).stem
        slides = text_to_slides(content)
        return [{"title": title, "content": content.strip(), "slides": slides, "language": "ro"}]
    except Exception as e:
        raise ImportError(f"PDF import failed: {e}")


# ── VideoPsalm .json ──────────────────────────────────────────────────────────

def import_videopasalm_json(filepath):
    enc = detect_encoding(filepath)
    with open(filepath, "r", encoding=enc, errors="replace") as f:
        data = json.load(f)

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and "songs" in data:
        items = data["songs"]
    elif isinstance(data, dict):
        items = [data]
    else:
        items = []

    songs = []
    for item in items:
        title = item.get("title", item.get("name", "Untitled"))
        language = item.get("language", item.get("lang", "ro"))
        verses = item.get("verses", item.get("strophes", item.get("parts", [])))
        slides = []
        for verse in verses:
            if isinstance(verse, dict):
                text = verse.get("text", verse.get("content", verse.get("lines", "")))
                if isinstance(text, list):
                    text = "\n".join(text)
            elif isinstance(verse, str):
                text = verse
            else:
                continue
            if text.strip():
                slides.append(text.strip())
        if not slides:
            slides = text_to_slides(item.get("content", item.get("text", "")))
        content = "\n\n".join(slides)
        songs.append({
            "title": title,
            "content": content,
            "slides": slides,
            "language": language,
            "author": item.get("author", item.get("composer", "")),
            "category": item.get("category", item.get("genre", "General")),
        })

    print(f"[VideoPsalm JSON] Found {len(songs)} songs")
    return songs


# ── VideoPsalm JSON — non-standard unquoted-key format ───────────────────────

def _parse_vp_manual(text):
    """
    Manual parser for non-standard VideoPsalm JSON (unquoted keys).
    Handles: {ID:1, Reference:"...", Verses:[{Text:"..."}]}
    """
    result = {"Songs": []}

    abbr_m = re.search(r'Abbreviation\s*:\s*"([^"]*)"', text)
    if abbr_m:
        result["Abbreviation"] = abbr_m.group(1)

    # Split into song blocks by ID:
    song_blocks = re.split(r'(?=\{?\s*ID\s*:\s*\d)', text)

    for block in song_blocks:
        song = {}

        id_m = re.search(r'ID\s*:\s*(\d+)', block)
        if id_m:
            song["ID"] = int(id_m.group(1))

        ref_m = re.search(r'Reference\s*:\s*"([^"]*)"', block)
        if ref_m:
            song["Reference"] = ref_m.group(1)

        title_m = re.search(r'Title\s*:\s*"([^"]*)"', block)
        if title_m:
            song["Title"] = title_m.group(1)

        author_m = re.search(r'Author\s*:\s*"([^"]*)"', block)
        if author_m:
            song["Author"] = author_m.group(1)

        # Extract verse texts
        verses = []
        for v in re.finditer(r'Text\s*:\s*"((?:[^"\\]|\\.)*)"', block):
            verse_text = (
                v.group(1)
                .replace("\\n", "\n")
                .replace("\\r", "")
                .replace('\\"', '"')
            )
            if verse_text.strip():
                verses.append({"Text": verse_text})

        song["Verses"] = verses
        if verses and song.get("ID"):
            result["Songs"].append(song)

    return result


def _vp_to_strict_json(text: str) -> str:
    """Convert VideoPsalm's relaxed JSON (unquoted keys + literal newlines inside
    string values) into strict JSON, respecting nesting. Walks char-by-char so a
    verse text containing "word, other:" is never mistaken for a key."""
    out = []
    i, n = 0, len(text)
    in_str = False
    esc = False
    while i < n:
        ch = text[i]
        if in_str:
            if esc:
                out.append(ch); esc = False
            elif ch == '\\':
                out.append(ch); esc = True
            elif ch == '"':
                out.append(ch); in_str = False
            elif ch == '\n':
                out.append('\\n')
            elif ch == '\r':
                out.append('\\r')
            elif ch == '\t':
                out.append('\\t')
            else:
                out.append(ch)
            i += 1
        else:
            if ch == '"':
                out.append(ch); in_str = True; i += 1
            elif ch.isalpha() or ch == '_':
                j = i
                while j < n and (text[j].isalnum() or text[j] == '_'):
                    j += 1
                word = text[i:j]
                k = j
                while k < n and text[k] in ' \t':
                    k += 1
                if k < n and text[k] == ':':
                    out.append('"' + word + '"')   # it's a key → quote it
                else:
                    out.append(word)               # bareword value (true/false/null)
                i = j
            else:
                out.append(ch); i += 1
    return ''.join(out)


def import_videopsalm_json(filepath):
    """
    Import a VideoPsalm JSON collection with potentially unquoted keys.
    Format: {Abbreviation: "AL", Songs: [{ID:1, Reference:"1", Verses:[{Text:"..."}], Text:"Title"}]}

    Attempts:
      1. Robust relaxed→strict JSON parser (_vp_to_strict_json) → json.loads()
      2. demjson3.decode()
      3. Manual regex parser (_parse_vp_manual)
    """
    print(f"[VP] Import: {filepath}")

    with open(filepath, "rb") as f:
        raw = f.read()

    # Strip BOM
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]

    text = raw.decode("utf-8", errors="replace")

    data = None

    # 1. Robust relaxed→strict conversion (handles nesting + multiline strings).
    try:
        data = json.loads(_vp_to_strict_json(text))
    except Exception as _e:
        print(f"[VP] strict-convert failed: {_e}")

    # 2. demjson3
    if data is None:
        try:
            import demjson3  # type: ignore
            data = demjson3.decode(text)
        except ImportError:
            pass
        except Exception:
            pass

    # 3. Manual parser
    if data is None:
        data = _parse_vp_manual(text)

    if not data or not data.get("Songs"):
        raise ImportError("Nu s-a putut parsa fișierul VideoPsalm JSON")

    abbreviation = data.get("Abbreviation", "")
    songs_data   = data.get("Songs", [])
    results = []

    for song in songs_data:
        verses = song.get("Verses", [])
        if not verses:
            continue

        author = song.get("Author", "") or ""

        slides = []
        for verse in verses:
            if isinstance(verse, dict):
                v_text = verse.get("Text") or verse.get("text") or ""
            else:
                v_text = str(verse)
            # Normalise literal \n sequences that survived JSON parsing
            v_text = v_text.replace("\\n", "\n").replace("\\r", "").strip()
            if v_text:
                slides.append(v_text)

        if not slides:
            continue

        # Title: VideoPsalm stores the song title in the song-level "Text" field
        # (a sibling of "Verses"). Prefer Title/Text; Reference is just an index
        # ("1","2"…) so it's a last resort; else the first verse line.
        raw_title = (song.get("Title") or song.get("Text") or "").strip()
        if not raw_title:
            first_line = slides[0].split("\n")[0].strip()
            raw_title = first_line or (song.get("Reference") or "").strip() or f"Cântare {song.get('ID', '')}"

        results.append({
            "title":    raw_title,
            "author":   author,
            "content":  "\n\n".join(slides),
            "slides":   slides,
            "language": "ro",
            "category": "General",
            "notes":    f"VideoPsalm {abbreviation}".strip(),
        })

    print(f"[VP] Import: {len(results)} cântări")
    return results


# ── VideoPsalm .xml ───────────────────────────────────────────────────────────

def import_videopasalm_xml(filepath_or_root, filename=""):
    if isinstance(filepath_or_root, ET.Element):
        root = filepath_or_root
    else:
        root = _try_parse_xml_with_encodings(filepath_or_root)
        if root is None:
            raise ImportError(f"Cannot parse XML: {filepath_or_root}")
        filename = str(filepath_or_root)

    songs = []
    song_nodes = (
        root.findall(".//song") or root.findall(".//Song") or [root]
    )

    for song_node in song_nodes:
        parsed = _parse_vpc_song_xml(song_node, filename)
        if parsed:
            songs.append(parsed)

    print(f"[VideoPsalm XML] Found {len(songs)} songs")
    return songs


def _parse_vpc_song_xml(song_node, filename=""):
    """
    Parse a single song XML node.
    Supports multiple VideoPsalm XML structures.
    """
    title = (
        song_node.get("title") or
        song_node.get("name") or
        _elem_text(song_node, "title") or
        _elem_text(song_node, "Title") or
        Path(filename).stem or
        "Untitled"
    )

    slides = []
    lyrics_node = song_node.find(".//lyrics") or song_node.find(".//Lyrics") or song_node

    verse_nodes = (
        lyrics_node.findall(".//verse") +
        lyrics_node.findall(".//Verse") +
        lyrics_node.findall(".//strophe") +
        lyrics_node.findall(".//stanza") +
        lyrics_node.findall(".//part")
    )

    # Remove duplicates while preserving order
    seen = set()
    unique_verses = []
    for v in verse_nodes:
        vid = id(v)
        if vid not in seen:
            seen.add(vid)
            unique_verses.append(v)

    for vn in unique_verses:
        lines_node = vn.find("lines") or vn.find("Lines")
        if lines_node is not None and lines_node.text:
            text = lines_node.text.replace("\\n", "\n").strip()
        else:
            line_nodes = vn.findall("line") + vn.findall("Line")
            if line_nodes:
                text = "\n".join(l.text.strip() for l in line_nodes if l.text and l.text.strip())
            else:
                text = ET.tostring(vn, encoding="unicode", method="text").strip()

        if text.strip():
            slides.append(text.strip())

    if not slides:
        all_text = ET.tostring(song_node, encoding="unicode", method="text").strip()
        slides = text_to_slides(all_text)

    if not slides:
        return None

    content = "\n\n".join(slides)
    return {
        "title": str(title).strip(),
        "content": content,
        "slides": slides,
        "language": song_node.get("language", song_node.get("lang", "ro")),
        "author": song_node.get("author", song_node.get("composer", _elem_text(song_node, "author") or "")),
        "category": song_node.get("category", "General"),
    }


def _elem_text(node, tag):
    """Return text of first matching child element, or None."""
    el = node.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return None


# ── VideoPsalm .vpc (ZIP of .song XML files) ─────────────────────────────────

def import_vpc(filepath):
    """
    Import a VideoPsalm .vpc file.
    .vpc is a ZIP archive containing .song files (XML) or other XML/JSON files.
    Falls back to plain XML or JSON if not a valid ZIP.
    """
    songs = []

    if zipfile.is_zipfile(filepath):
        with zipfile.ZipFile(filepath, "r") as z:
            names = z.namelist()
            print(f"[VPC] ZIP contents ({len(names)} files): {names[:20]}")

            # Priority: .song files, then .xml, then anything without a system prefix
            def priority(n):
                ext = Path(n).suffix.lower()
                if ext == ".song":
                    return 0
                if ext == ".xml":
                    return 1
                if n.startswith("__") or n.startswith("."):
                    return 99
                return 5

            candidate_files = sorted(
                [n for n in names if not n.endswith("/")],
                key=priority
            )

            for name in candidate_files:
                if priority(name) >= 99:
                    continue
                try:
                    with z.open(name) as f:
                        raw = f.read()
                    if not raw.strip():
                        continue

                    # Try XML
                    root = _try_parse_xml_with_encodings(raw)
                    if root is not None:
                        # Single song node or collection
                        if root.tag.lower() in ("song", "songs", "songbase", "songbook", "hymnal"):
                            if root.tag.lower() == "song":
                                parsed = _parse_vpc_song_xml(root, name)
                                if parsed:
                                    songs.append(parsed)
                            else:
                                for sn in root.findall(".//song") + root.findall(".//Song"):
                                    parsed = _parse_vpc_song_xml(sn, name)
                                    if parsed:
                                        songs.append(parsed)
                        else:
                            # Try as multi-song root
                            song_nodes = root.findall(".//song") + root.findall(".//Song")
                            if song_nodes:
                                for sn in song_nodes:
                                    parsed = _parse_vpc_song_xml(sn, name)
                                    if parsed:
                                        songs.append(parsed)
                            else:
                                parsed = _parse_vpc_song_xml(root, name)
                                if parsed:
                                    songs.append(parsed)
                        continue

                    # Try JSON
                    try:
                        text = raw.decode("utf-8", errors="replace")
                        data = json.loads(text)
                        items = data if isinstance(data, list) else data.get("songs", [data])
                        for item in items:
                            title = item.get("title", item.get("name", Path(name).stem))
                            verses = item.get("verses", item.get("strophes", []))
                            slides = []
                            for v in verses:
                                t = v.get("text", v.get("content", "")) if isinstance(v, dict) else v
                                if t:
                                    slides.append(str(t).strip())
                            if not slides:
                                slides = text_to_slides(item.get("content", ""))
                            if slides:
                                songs.append({
                                    "title": str(title),
                                    "content": "\n\n".join(slides),
                                    "slides": slides,
                                    "language": item.get("language", "ro"),
                                    "author": item.get("author", ""),
                                    "category": "General",
                                })
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass

                except Exception as e:
                    print(f"[VPC] Error processing '{name}': {e}")

        print(f"[VPC] Total songs imported from ZIP: {len(songs)}")
        if songs:
            return songs

    # Not a ZIP (or ZIP was empty) — try plain XML/JSON
    print("[VPC] Not a valid ZIP or no songs found in ZIP, trying plain XML/JSON")
    try:
        return import_videopasalm_xml(filepath)
    except Exception:
        pass
    try:
        return import_videopasalm_json(filepath)
    except Exception:
        pass

    # Last resort: show first 200 bytes for diagnosis
    with open(filepath, "rb") as f:
        preview = f.read(200)
    print(f"[VPC] Could not parse. First 200 bytes: {preview!r}")
    return []


# ── EasyWorship .ewsx (ZIP archive) ──────────────────────────────────────────

def import_easyworship_ewsx(filepath):
    songs = []
    try:
        with zipfile.ZipFile(filepath, "r") as z:
            names = z.namelist()
            print(f"[EWSX] ZIP contents: {names[:20]}")
            xml_files = [n for n in names if n.lower().endswith((".xml", ".json"))]
            for name in xml_files:
                with z.open(name) as f:
                    raw = f.read()
                try:
                    data = json.loads(raw.decode("utf-8", errors="replace"))
                    items = data.get("songs", [data]) if isinstance(data, dict) else data
                    for item in items:
                        title = item.get("title", Path(name).stem)
                        slides_raw = item.get("slides", item.get("verses", []))
                        slides = [s if isinstance(s, str) else s.get("text", "") for s in slides_raw]
                        slides = [s.strip() for s in slides if s.strip()]
                        if not slides:
                            slides = text_to_slides(item.get("content", ""))
                        songs.append({
                            "title": title, "content": "\n\n".join(slides),
                            "slides": slides, "language": "ro",
                            "author": "", "category": "General",
                        })
                except (json.JSONDecodeError, Exception):
                    root = _try_parse_xml_with_encodings(raw)
                    if root is not None:
                        for sn in (root.findall(".//song") + root.findall(".//Song")) or [root]:
                            title = sn.get("title", sn.get("name", Path(name).stem))
                            slides = []
                            for slide in sn.findall(".//slide") + sn.findall(".//Slide") + sn.findall(".//verse"):
                                text = ET.tostring(slide, encoding="unicode", method="text").strip()
                                if text:
                                    slides.append(text)
                            if not slides:
                                slides = text_to_slides(
                                    ET.tostring(sn, encoding="unicode", method="text").strip()
                                )
                            songs.append({
                                "title": title, "content": "\n\n".join(slides),
                                "slides": slides, "language": "ro",
                                "author": "", "category": "General",
                            })
    except zipfile.BadZipFile:
        print("[EWSX] Not a ZIP, trying as SQLite DB")
        songs = import_easyworship_db(filepath)
    print(f"[EWSX] Found {len(songs)} songs")
    return songs


# ── EasyWorship .db (SQLite) ──────────────────────────────────────────────────

def import_easyworship_db(filepath):
    songs = []
    try:
        conn = sqlite3.connect(filepath)
        conn.row_factory = sqlite3.Row

        # List ALL tables and their columns
        tables = [
            r[0] for r in
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        print(f"[EasyWorship DB] All tables: {tables}")

        for tbl in tables:
            try:
                cols = [
                    row[1] for row in
                    conn.execute(f"PRAGMA table_info({tbl})").fetchall()
                ]
                print(f"[EasyWorship DB] Table '{tbl}': columns = {cols}")
            except Exception as col_err:
                print(f"[EasyWorship DB] Cannot inspect '{tbl}': {col_err}")

        # Find the song table — EW6/7 uses "song", older versions may differ
        song_table = None
        for candidate in tables:
            cl = candidate.lower()
            if cl in ("song", "songs", "presentation", "presentations"):
                song_table = candidate
                break
        if song_table is None:
            song_table = next(
                (t for t in tables if "song" in t.lower() or "present" in t.lower()),
                None
            )

        if song_table is None:
            print("[EasyWorship DB] No song table found!")
            conn.close()
            return songs

        print(f"[EasyWorship DB] Using table: '{song_table}'")
        rows = conn.execute(f"SELECT * FROM {song_table} LIMIT 500").fetchall()
        print(f"[EasyWorship DB] Rows in '{song_table}': {len(rows)}")

        for row in rows:
            d = dict(row)

            # Title: try common column names
            title = (
                d.get("title") or d.get("Title") or d.get("name") or
                d.get("Name") or d.get("song_title") or "Untitled"
            )

            # Lyrics: try common column names
            content_raw = (
                d.get("words") or d.get("Words") or
                d.get("lyrics") or d.get("Lyrics") or
                d.get("content") or d.get("Content") or
                d.get("text") or d.get("Text") or
                d.get("SongText") or d.get("songtext") or ""
            )

            if not content_raw:
                # Try any column that looks like it could have lyrics
                for col, val in d.items():
                    if isinstance(val, str) and len(val) > 20 and col.lower() not in (
                        "title", "author", "copyright", "guid", "background",
                        "modified", "created", "category", "notes"
                    ):
                        content_raw = val
                        print(f"[EasyWorship DB] Using fallback column '{col}' for lyrics")
                        break

            if not content_raw:
                continue

            content_str = str(content_raw)

            # Strip RTF if needed
            if content_str.lstrip().startswith("{\\rtf"):
                content_str = strip_rtf(content_str)

            slides = text_to_slides(content_str)
            content = "\n\n".join(slides)

            author = str(d.get("author", d.get("Author", d.get("music_author", ""))) or "")
            songs.append({
                "title": str(title),
                "content": content,
                "slides": slides,
                "language": "ro",
                "author": author,
                "category": "General",
            })

        conn.close()
    except Exception as e:
        print(f"[EasyWorship DB] Error: {e}")

    print(f"[EasyWorship DB] Imported {len(songs)} songs")
    return songs


# ── EasyWorship 7 (.db with JSON lyrics) ─────────────────────────────────────

def detect_easyworship7_default_path():
    """Return the default EW7 song.db path if it exists on this machine."""
    docs = Path.home() / "Documents"
    candidates = [
        docs / "Easyworship" / "Default" / "Databases" / "Data" / "song.db",
        docs / "EasyWorship" / "Default" / "Databases" / "Data" / "song.db",
        Path("C:/Users") / os.environ.get("USERNAME", "") / "Documents" / "Easyworship" / "Default" / "Databases" / "Data" / "song.db",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def _parse_ew7_json_lyrics(raw) -> list[str]:
    """
    Parse EasyWorship 7 JSON lyrics field.
    Format: {"slides": [{"text": "...", "label": "Verse 1"}, ...]}
    Returns list of slide texts.
    """
    if not raw:
        return []

    # It may already be a dict (if sqlite3 decoded JSON automatically)
    if isinstance(raw, dict):
        data = raw
    else:
        raw_str = str(raw).strip()
        if not raw_str.startswith("{"):
            return []
        try:
            data = json.loads(raw_str)
        except (json.JSONDecodeError, ValueError):
            return []

    slides = data.get("slides", [])
    result = []
    for slide in slides:
        if isinstance(slide, dict):
            text = slide.get("text", slide.get("body", slide.get("content", "")))
        else:
            text = str(slide)
        text = text.strip()
        if text:
            result.append(text)
    return result


def import_easyworship7_db(filepath, progress_callback=None):
    """
    Import songs from an EasyWorship 7 song.db SQLite database.
    EW7 stores lyrics as JSON: {"slides": [{"text": "...", "label": "..."}, ...]}
    progress_callback(current, total) called periodically.
    """
    songs = []
    try:
        conn = sqlite3.connect(filepath)
        conn.row_factory = sqlite3.Row

        tables = [
            r[0] for r in
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        print(f"[EW7] Tables: {tables}")

        # EW7 uses table named "song"
        song_table = next(
            (t for t in tables if t.lower() in ("song", "songs")), None
        )
        if song_table is None:
            print("[EW7] No 'song' table found, falling back to EW6 importer")
            conn.close()
            return import_easyworship_db(filepath)

        cols = [row[1] for row in conn.execute(f"PRAGMA table_info({song_table})").fetchall()]
        print(f"[EW7] Columns in '{song_table}': {cols}")

        rows = conn.execute(f"SELECT * FROM {song_table}").fetchall()
        total = len(rows)
        print(f"[EW7] Total rows: {total}")

        for i, row in enumerate(rows):
            d = dict(row)

            title = (
                d.get("title") or d.get("Title") or d.get("name") or "Untitled"
            )
            author = str(d.get("author", d.get("music_author", "")) or "")
            copyright_ = str(d.get("copyright", "") or "")

            # EW7 lyrics column is usually 'lyrics' or 'words'
            lyrics_raw = (
                d.get("lyrics") or d.get("Lyrics") or
                d.get("words") or d.get("Words") or
                d.get("content") or d.get("text") or ""
            )

            slides = []

            # Try JSON parse first (EW7 format)
            if lyrics_raw:
                lyrics_str = str(lyrics_raw).strip()
                if lyrics_str.startswith("{"):
                    slides = _parse_ew7_json_lyrics(lyrics_str)
                elif lyrics_str.lstrip().startswith("{\\rtf"):
                    stripped = strip_rtf(lyrics_str)
                    slides = text_to_slides(stripped)
                else:
                    slides = text_to_slides(lyrics_str)

            if not slides:
                continue

            content = "\n\n".join(slides)
            songs.append({
                "title": str(title).strip(),
                "content": content,
                "slides": slides,
                "language": "ro",
                "author": author.strip(),
                "category": "General",
                "notes": copyright_.strip(),
            })

            if progress_callback and i % 50 == 0:
                progress_callback(i + 1, total)

        conn.close()
        if progress_callback:
            progress_callback(total, total)

    except Exception as e:
        print(f"[EW7] Error: {e}")
        import traceback
        traceback.print_exc()

    print(f"[EW7] Imported {len(songs)} songs")
    return songs


# ── EasyWorship 7 two-file RTF layout (Songs.db + SongWords.db) ──────────────

def import_easyworship7(songs_db_path, words_db_path, progress_callback=None):
    """
    Import EasyWorship 7 split-DB layout where:
      Songs.db   → table 'song': rowid, title, author, copyright
      SongWords.db → table 'word': rowid, song_id (= rowid from Songs.db), words (RTF)

    Uses striprtf for RTF → plain text, then parses Verse/Chorus/Bridge labels.
    Falls back to import_easyworship7_twofile() if striprtf is unavailable or
    the 'word' table is not found.
    """
    try:
        from striprtf.striprtf import rtf_to_text as _rtf_to_text
    except ImportError:
        print("[EW7] striprtf not installed — falling back to twofile importer")
        return import_easyworship7_twofile(songs_db_path, words_db_path, progress_callback)

    print(f"[EW7] Songs: {songs_db_path}")
    print(f"[EW7] Words: {words_db_path}")

    LABEL_RE = re.compile(
        r'^(Verse|Chorus|Bridge|Intro|Outro|Pre-Chorus|Tag|Ending)\s*\d*\s*$',
        re.IGNORECASE,
    )

    # ── Load song metadata keyed by rowid ────────────────────────────────────
    songs_conn = sqlite3.connect(songs_db_path)
    songs_conn.row_factory = sqlite3.Row
    songs_map = {}
    try:
        for row in songs_conn.execute(
            "SELECT rowid, title, author, copyright FROM song"
        ):
            songs_map[row["rowid"]] = {
                "title":     row["title"]     or "",
                "author":    row["author"]    or "",
                "copyright": row["copyright"] or "",
            }
    except Exception as e:
        print(f"[EW7] Cannot read Songs.db: {e}")
        songs_conn.close()
        return import_easyworship7_twofile(songs_db_path, words_db_path, progress_callback)
    songs_conn.close()
    print(f"[EW7] {len(songs_map)} titles loaded")

    # ── Load RTF words keyed by song_id ──────────────────────────────────────
    words_conn = sqlite3.connect(words_db_path)
    words_conn.row_factory = sqlite3.Row

    # Check the table name — some builds use 'word', others 'SongWords'
    w_tables = [r[0] for r in words_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    print(f"[EW7] SongWords tables: {w_tables}")
    word_table = next(
        (t for t in w_tables if t.lower() in ("word", "words", "songwords")), None
    )
    if word_table is None:
        print("[EW7] 'word' table not found — falling back to twofile importer")
        words_conn.close()
        return import_easyworship7_twofile(songs_db_path, words_db_path, progress_callback)

    results = []
    all_rows = words_conn.execute(
        f"SELECT song_id, words FROM {word_table}"
    ).fetchall()
    total = len(all_rows)

    for i, row in enumerate(all_rows):
        song_id = row["song_id"]
        rtf     = row["words"] or ""
        meta    = songs_map.get(song_id, {})
        title   = meta.get("title", "")
        if not title:
            continue

        # Strip RTF → plain text
        try:
            text = _rtf_to_text(rtf).strip()
        except Exception:
            text = strip_rtf(rtf)   # fallback to built-in

        if not text:
            continue

        # Parse slides by section label
        slides = []
        current_lines = []

        for line in text.splitlines():
            stripped = line.strip()
            if LABEL_RE.match(stripped):
                if current_lines:
                    chunk = "\n".join(current_lines).strip()
                    if chunk:
                        slides.append(chunk)
                    current_lines = []
            elif not stripped:
                if current_lines:
                    chunk = "\n".join(current_lines).strip()
                    if chunk:
                        slides.append(chunk)
                    current_lines = []
            else:
                current_lines.append(stripped)

        if current_lines:
            chunk = "\n".join(current_lines).strip()
            if chunk:
                slides.append(chunk)

        slides = [s for s in slides if len(s.strip()) > 2]

        if not slides:
            # Fallback: chunk by 4 lines
            all_lines = [l for l in text.splitlines() if l.strip()]
            for idx in range(0, len(all_lines), 4):
                chunk = all_lines[idx:idx + 4]
                if chunk:
                    slides.append("\n".join(chunk))

        if not slides:
            continue

        results.append({
            "title":    title,
            "author":   meta.get("author", ""),
            "content":  "\n\n".join(slides),
            "slides":   slides,
            "language": "ro",
            "category": "General",
            "notes":    meta.get("copyright", ""),
        })

        if progress_callback and i % 50 == 0:
            progress_callback(i + 1, total)

    words_conn.close()
    if progress_callback:
        progress_callback(total, total)

    print(f"[EW7] Import: {len(results)} cântări")
    return results


# ── EasyWorship 7 two-file layout (Songs.db + SongsWords.db) ─────────────────

def import_easyworship7_twofile(songs_db_path, words_db_path, progress_callback=None):
    """
    Import songs from EasyWorship 7's split-database layout.

    songs_db_path  – path to Songs.db   (table 'song': uid, title, author, copyright)
    words_db_path  – path to SongsWords.db (table 'song_slide': uid FK, ordinal, RTF content)

    Returns a list of song dicts compatible with db.add_song().
    """
    songs = []
    try:
        conn_s = sqlite3.connect(songs_db_path)
        conn_s.row_factory = sqlite3.Row
        conn_w = sqlite3.connect(words_db_path)
        conn_w.row_factory = sqlite3.Row

        # ── Discover tables ──────────────────────────────────────────────────
        s_tables = [r[0] for r in conn_s.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        w_tables = [r[0] for r in conn_w.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        print(f"[EW7-2F] Songs.db tables:      {s_tables}")
        print(f"[EW7-2F] SongsWords.db tables: {w_tables}")

        # ── Song metadata table (Songs.db) ───────────────────────────────────
        song_table = next(
            (t for t in s_tables if t.lower() in ("song", "songs")), None
        )
        if song_table is None:
            song_table = next(
                (t for t in s_tables if "song" in t.lower()), None
            )
        if song_table is None:
            print("[EW7-2F] No song table found in Songs.db — aborting")
            conn_s.close(); conn_w.close()
            return songs

        s_cols = [r[1] for r in conn_s.execute(f"PRAGMA table_info({song_table})").fetchall()]
        print(f"[EW7-2F] '{song_table}' columns: {s_cols}")

        song_rows = conn_s.execute(f"SELECT * FROM {song_table}").fetchall()
        total = len(song_rows)
        print(f"[EW7-2F] Total songs in metadata table: {total}")

        # uid → {title, author, copyright}
        meta_map = {}
        for row in song_rows:
            d = dict(row)
            uid = (d.get("song_uid") or d.get("uid") or
                   d.get("SongUID") or d.get("id") or d.get("rowid"))
            title = (d.get("title") or d.get("Title") or
                     d.get("name") or "Untitled")
            author = str(d.get("author") or d.get("music_author") or "")
            copyright_ = str(d.get("copyright") or "")
            if uid is not None:
                meta_map[uid] = {
                    "title": str(title).strip(),
                    "author": author.strip(),
                    "copyright": copyright_.strip(),
                }

        # ── Slide table (SongsWords.db) ──────────────────────────────────────
        slide_table = next(
            (t for t in w_tables
             if t.lower() in ("song_slide", "songslide", "slide", "slides")),
            None,
        )
        if slide_table is None:
            slide_table = next(
                (t for t in w_tables if "slide" in t.lower() or "word" in t.lower()),
                None,
            )

        slides_by_uid: dict = {}   # uid → [(ordinal, text), …]
        if slide_table is not None:
            w_cols = [r[1] for r in conn_w.execute(
                f"PRAGMA table_info({slide_table})"
            ).fetchall()]
            print(f"[EW7-2F] '{slide_table}' columns: {w_cols}")

            slide_rows = conn_w.execute(
                f"SELECT * FROM {slide_table} ORDER BY rowid"
            ).fetchall()
            for row in slide_rows:
                d = dict(row)
                uid = (d.get("song_uid") or d.get("SongUID") or
                       d.get("uid") or d.get("song_id"))
                ordinal = int(
                    d.get("slide_number") or d.get("ordinal") or
                    d.get("position") or d.get("order") or 0
                )
                raw = (
                    d.get("slide_content") or d.get("content") or
                    d.get("lyrics") or d.get("words") or
                    d.get("text") or ""
                )
                text = str(raw).strip() if raw else ""
                # Strip RTF if present
                if text.lstrip().startswith("{\\rtf"):
                    text = strip_rtf(text)
                if text and uid is not None:
                    slides_by_uid.setdefault(uid, []).append((ordinal, text))
        else:
            print("[EW7-2F] No slide table found in SongsWords.db")

        conn_s.close()
        conn_w.close()

        # ── Assemble song dicts ──────────────────────────────────────────────
        for i, (uid, meta) in enumerate(meta_map.items()):
            raw_slides = slides_by_uid.get(uid, [])
            raw_slides.sort(key=lambda x: x[0])          # sort by ordinal
            slide_texts = [s for _, s in raw_slides if s]

            if not slide_texts:
                # Slides DB had no rows for this UID — skip gracefully
                continue

            content = "\n\n".join(slide_texts)
            songs.append({
                "title":    meta["title"],
                "content":  content,
                "slides":   slide_texts,
                "language": "ro",
                "author":   meta["author"],
                "category": "General",
                "notes":    meta["copyright"],
            })

            if progress_callback and i % 50 == 0:
                progress_callback(i + 1, total)

        if progress_callback:
            progress_callback(total, total)

    except Exception as e:
        print(f"[EW7-2F] Error: {e}")
        import traceback
        traceback.print_exc()

    print(f"[EW7-2F] Imported {len(songs)} songs")
    return songs


# ── Import de biblii din fișiere — ELIMINAT ───────────────────────────────────
# Importul de biblii din fișiere externe a fost eliminat complet (împreună cu
# dependința auxiliară de citire a bazelor de date). Vizualizarea bibliilor deja
# existente în profil rămâne disponibilă; nu se mai pot importa biblii din fișiere.


# ── Universal dispatcher ──────────────────────────────────────────────────────

def import_file(filepath):
    """Auto-detect format and import. Returns {"type": "songs"/"bible", "data": ...}"""
    ext = Path(filepath).suffix.lower()
    size = os.path.getsize(filepath)
    print(f"\n[import_file] File: {filepath}")
    print(f"[import_file] Extension: {ext}  Size: {size} bytes")

    if ext == ".txt":
        data = import_txt(filepath)
        print(f"[import_file] Result: {len(data)} songs")
        return {"type": "songs", "data": data}

    elif ext == ".docx":
        data = import_docx(filepath)
        print(f"[import_file] Result: {len(data)} songs")
        return {"type": "songs", "data": data}

    elif ext == ".pdf":
        data = import_pdf(filepath)
        print(f"[import_file] Result: {len(data)} songs")
        return {"type": "songs", "data": data}

    elif ext == ".json":
        # Try new VP JSON (unquoted-key format) first, then legacy parser
        try:
            data = import_videopsalm_json(filepath)
            if data:
                print(f"[import_file] Result: {len(data)} songs (VP JSON)")
                return {"type": "songs", "data": data}
        except Exception:
            pass
        data = import_videopasalm_json(filepath)
        print(f"[import_file] Result: {len(data)} songs")
        return {"type": "songs", "data": data}

    elif ext == ".xml":
        data = import_videopasalm_xml(filepath)
        print(f"[import_file] Result: {len(data)} songs")
        return {"type": "songs", "data": data}

    elif ext == ".vpc":
        data = import_vpc(filepath)
        if not data:
            with open(filepath, "rb") as f:
                preview = f.read(200)
            print(f"[import_file] WARNING: 0 songs from .vpc. First 200 bytes: {preview!r}")
        else:
            print(f"[import_file] Result: {len(data)} songs")
        return {"type": "songs", "data": data}

    elif ext in (".ewsx", ".db"):
        if zipfile.is_zipfile(filepath):
            data = import_easyworship_ewsx(filepath)
        else:
            data = import_easyworship_db(filepath)
        if not data:
            with open(filepath, "rb") as f:
                preview = f.read(200)
            print(f"[import_file] WARNING: 0 songs from EasyWorship. First 200 bytes: {preview!r}")
        else:
            print(f"[import_file] Result: {len(data)} songs")
        return {"type": "songs", "data": data}

    else:
        # Unknown extension — try heuristics
        print(f"[import_file] Unknown extension '{ext}', trying heuristics")
        if zipfile.is_zipfile(filepath):
            print("[import_file] Detected ZIP, trying as .vpc")
            data = import_vpc(filepath)
            if data:
                return {"type": "songs", "data": data}
        try:
            conn = sqlite3.connect(filepath)
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            conn.close()
            if tables:
                print(f"[import_file] Detected SQLite with tables: {tables}")
                if any("song" in t.lower() for t in tables):
                    return {"type": "songs", "data": import_easyworship_db(filepath)}
                # Import de biblii din baze de date (book/verse) — ELIMINAT;
                # nu mai cităm tabele de biblie din fișiere.
        except Exception:
            pass
        raise ValueError(f"Unsupported file format: {ext}")
