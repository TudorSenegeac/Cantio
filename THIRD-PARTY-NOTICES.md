# Cantio — Third-Party Notices

Cantio bundles the following third-party components. Their licenses govern those
components and, in some cases, impose obligations on Cantio as a whole.

## Cantio is licensed under GPL v3 — PyQt6/Qt are fully covered

**Cantio itself is free and open-source under the GNU GPL v3 (see LICENSE).**

Cantio's UI uses **PyQt6** (Riverbank) on top of **Qt** (The Qt Company), which are
dual-licensed **GPL v3 OR commercial**. Because Cantio is released under **GPL v3**,
using PyQt6/Qt under their **GPL v3** option is fully compliant — **no purchase or
commercial license is needed.** ✅

The only obligation is the normal GPL one: make Cantio's **source code available**
to anyone who receives the app (this repo satisfies that). All other components
below are permissive (MIT/BSD/Apache) and impose no extra conditions.

## Python components

| Component | License | Commercial-friendly |
|---|---|---|
| PyQt6 / PyQt6-Qt6 / PyQt6-sip | GPL v3 **or** commercial | ⚠ see above |
| Flask, flask-socketio, flask-cors | BSD-3-Clause | ✅ |
| requests | Apache-2.0 | ✅ |
| beautifulsoup4 | MIT | ✅ |
| lxml | BSD-3-Clause | ✅ |
| striprtf | BSD | ✅ |
| python-docx | MIT | ✅ |
| pypdf | BSD-3-Clause | ✅ |
| qrcode | BSD | ✅ |
| Pillow | MIT-CMU (HPND) | ✅ |
| websocket-client | Apache-2.0 | ✅ |
| PyInstaller (build) | GPL w/ bootloader exception (runtime not affected) | ✅ (for shipping frozen apps) |
| faster-whisper (optional, dynamic BETA) | MIT | ✅ |
| yt-dlp (optional, dynamic BETA) | Unlicense/public-domain | ✅ |
| mido / python-rtmidi (optional, MIDI) | MIT | ✅ |

## Electron / JS components

| Component | License |
|---|---|
| Electron | MIT |
| ws | MIT |
| @electron/packager (build) | BSD-2-Clause |

## Bundled fonts (display-electron/fonts/)

All 100+ families are from **Google Fonts** and are redistributable, licensed
under either the **SIL Open Font License 1.1 (OFL)**, **Apache License 2.0**, or
the **Ubuntu Font License**. Redistribution is allowed; keep the per-font license
files (Google ships them with each family) alongside the WOFF2 files. Re-run
`python download_fonts.py` to refresh, and consider committing the upstream
`OFL.txt`/`LICENSE.txt` for each family into `display-electron/fonts/licenses/`.

## Content note

Bible translations, song lyrics, and imported media are NOT covered by this
software license — you are responsible for the rights to any content you display
or ship (e.g. CCLI reporting for copyrighted worship songs).
