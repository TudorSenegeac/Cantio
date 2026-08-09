# cantio.spec — PyInstaller build spec for Cantio
# Run with: pyinstaller --clean cantio.spec

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

is_win   = sys.platform == 'win32'
is_mac   = sys.platform == 'darwin'
is_linux = sys.platform.startswith('linux')

# ── Data files ────────────────────────────────────────────────────────────────
datas = []

for asset in ('GProICON.png', 'GProICON.ico', 'GProICON.icns',
              'SplashScreen.png', 'LICENSE', 'THIRD-PARTY-NOTICES.md'):
    if os.path.exists(asset):
        datas.append((asset, '.'))

if os.path.exists('GPSPLASH-cutout.png'):
    datas.append(('GPSPLASH-cutout.png', '.'))

if is_win and os.path.exists('mdbtools'):
    datas.append(('mdbtools', 'mdbtools'))

# display-electron este compilat separat cu electron-packager → dist/Cantio/CantioDisplay/
# Nu se include în PyInstaller datas; build.py copiază executabilul compilat lângă Cantio.exe.

# ── Hidden imports ────────────────────────────────────────────────────────────
hiddenimports = [
    # PyQt6
    'PyQt6',
    'PyQt6.QtWidgets',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtMultimedia',
    'PyQt6.QtMultimediaWidgets',
    'PyQt6.QtNetwork',
    'PyQt6.QtWebSockets',
    'PyQt6.sip',
    # Database
    'sqlite3',
    # Web / Remote
    'flask',
    'flask_socketio',
    'engineio',
    'socketio',
    'engineio.async_drivers.threading',
    'flask_cors',
    'werkzeug',
    'werkzeug.serving',
    'werkzeug.routing',
    'werkzeug.middleware',
    # Import formats
    'striprtf',
    'striprtf.striprtf',
    'requests',
    'bs4',
    'lxml',
    'lxml.etree',
    'docx',
    'pypdf',
    # QR code
    'qrcode',
    'qrcode.image.pil',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    # Camera
    'cv2',
    # WebSocket client
    'websocket',
    'websocket._app',
    'websocket._core',
    # stdlib (some versions need explicit listing)
    'json',
    'hashlib',
    'threading',
    'subprocess',
    'pathlib',
    'shutil',
    'tempfile',
    'platform',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'test',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Icon selection ────────────────────────────────────────────────────────────
if is_win:
    # Prefer .ico; fall back to .png (PyInstaller 6+ accepts PNG on Windows)
    icon_file = 'GProICON.ico' if os.path.exists('GProICON.ico') else 'GProICON.png'
elif is_mac:
    icon_file = 'GProICON.icns' if os.path.exists('GProICON.icns') else 'GProICON.png'
else:
    icon_file = 'GProICON.png'

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Cantio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
    version='version_info.txt' if os.path.exists('version_info.txt') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Cantio',
)

if is_mac:
    app = BUNDLE(
        coll,
        name='Cantio.app',
        icon='GProICON.icns' if os.path.exists('GProICON.icns') else 'GProICON.png',
        bundle_identifier='com.cantio.app',
        info_plist={
            'NSHighResolutionCapable': True,
            'NSCameraUsageDescription':
                'Cantio folosește camera pentru fundal video live.',
            'NSMicrophoneUsageDescription':
                'Cantio poate accesa microfonul pentru audio.',
            'CFBundleShortVersionString': '1.5.2',
            'CFBundleVersion': '1.5.2',
            'LSMinimumSystemVersion': '10.14',
        },
    )
