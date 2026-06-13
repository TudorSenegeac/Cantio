# Cantio 🎵

Church lyrics display software for Windows.

## Features
- 🎵 Song library with search (SQLite database)
- 📖 Bible verse display (import .bib from BibleShow)
- 📺 Fullscreen display on projector/second monitor
- 👁 Live preview in control window
- ⬆ Import from: TXT, DOCX, PDF, VideoPsalm (.json/.xml), EasyWorship (.ewsx/.db)
- 🎨 Fully customizable appearance (font, colors, background image, shadow, outline)
- 🌍 Unicode support: Romanian, Church Slavonic, Greek
- ⚡ Fade/instant transitions

## Run directly (development)

```bash
pip install PyQt6 python-docx pymupdf lxml
python main.py
```

## Build .exe for Windows

Double-click `build.bat` or run:
```bash
pip install pyinstaller
pyinstaller Cantio.spec --clean
```
The `.exe` will appear in the `dist/` folder.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Space / Enter | Go Live (send current slide) |
| → / ↓ | Next slide |
| ← / ↑ | Previous slide |
| Escape | Black screen |

## File Structure

```
Cantio/
├── main.py              # Entry point
├── control_window.py    # Operator control panel
├── display_window.py    # Projector fullscreen window
├── preview_widget.py    # Live preview widget
├── settings_dialog.py   # Display settings dialog
├── database.py          # SQLite data layer
├── importer.py          # File format importers
├── Cantio.spec          # PyInstaller build config
├── build.bat            # Windows build script
└── requirements.txt     # Python dependencies
```

## Data storage
All songs and settings are saved in `%USERPROFILE%\Cantio\cantio.db`
