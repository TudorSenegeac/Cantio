"""
Cantio — offline font bundler.
Downloads the WOFF2 files for every family in fonts.js (latin + latin-ext
subsets, weights 400/700) into display-electron/fonts/ and writes a local
cantio-fonts.css with @font-face rules pointing at the local files, so the app
renders its fonts with NO internet connection.

Run once at build/setup time:  python download_fonts.py
Re-run is safe (skips files already downloaded).
"""
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS_JS = os.path.join(HERE, "display-electron", "fonts.js")
OUT_DIR = os.path.join(HERE, "display-electron", "fonts")
FILES_DIR = os.path.join(OUT_DIR, "files")
CSS_OUT = os.path.join(OUT_DIR, "cantio-fonts.css")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
KEEP_SUBSETS = ("latin", "latin-ext")   # Romanian diacritics live in latin-ext


def _families():
    """Read the FONTS list straight out of fonts.js."""
    txt = open(FONTS_JS, encoding="utf-8").read()
    m = re.search(r"const FONTS = \[(.*?)\];", txt, re.S)
    return re.findall(r"'([^']+)'", m.group(1)) if m else []


def _fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req, timeout=25).read()
    return data if binary else data.decode("utf-8")


def main():
    os.makedirs(FILES_DIR, exist_ok=True)
    families = _families()
    print(f"[fonts] {len(families)} families → {OUT_DIR}")
    css_blocks = []
    ok = 0
    fail = []
    for fam in families:
        try:
            url = ("https://fonts.googleapis.com/css2?family="
                   + fam.replace(" ", "+") + ":wght@400;700&display=swap")
            css = _fetch(url)
        except Exception as e:
            fail.append(fam); print(f"  [X] {fam}: css {e}"); continue

        # Split into (subset-comment, @font-face block) pairs.
        parts = re.split(r"/\*\s*([\w-]+)\s*\*/", css)
        n = 0
        # parts = [pre, subset1, block1, subset2, block2, ...]
        for i in range(1, len(parts) - 1, 2):
            subset = parts[i].strip()
            block = parts[i + 1]
            if subset not in KEEP_SUBSETS:
                continue
            m = re.search(r"src:\s*url\((https://[^)]+\.woff2)\)", block)
            if not m:
                continue
            woff_url = m.group(1)
            fname = re.sub(r"[^A-Za-z0-9]+", "_", fam) + f"_{subset}_" + woff_url.split("/")[-1]
            fpath = os.path.join(FILES_DIR, fname)
            if not os.path.exists(fpath):
                try:
                    open(fpath, "wb").write(_fetch(woff_url, binary=True))
                except Exception as e:
                    print(f"  [X] {fam}/{subset}: woff2 {e}"); continue
            block_local = block.replace(woff_url, f"./files/{fname}")
            css_blocks.append(f"/* {fam} — {subset} */\n{block_local.strip()}")
            n += 1
        if n:
            ok += 1
            print(f"  [OK] {fam} ({n} files)")
        else:
            fail.append(fam)

    open(CSS_OUT, "w", encoding="utf-8").write("\n\n".join(css_blocks))
    print(f"\n[fonts] done: {ok}/{len(families)} families | css: {CSS_OUT}")
    if fail:
        print("[fonts] failed:", ", ".join(fail))


if __name__ == "__main__":
    main()
