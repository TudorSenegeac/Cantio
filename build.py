#!/usr/bin/env python3
"""
Cantio Build Script
Compilează aplicația pentru Windows, Mac și Linux.

Utilizare:
  python build.py          # meniu interactiv
  python build.py all      # build complet
  python build.py python   # doar PyInstaller
  python build.py electron # doar Electron Display
  python build.py installer # doar instalator
  python build.py clean    # curăță și rebuild total
"""

import os
import sys
import shutil
import subprocess
import platform
import json
from pathlib import Path

# GitHub Actions pe Windows folosește cp1252 — forțăm UTF-8 pentru diacritice
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BUILD_DIR = Path("build")
DIST_DIR  = Path("dist")

# ── Helpers ───────────────────────────────────────────────────────────────────

def run(cmd, cwd=None, check=True):
    """Rulează o comandă și afișează output în timp real."""
    display = ' '.join(cmd) if isinstance(cmd, list) else cmd
    print(f"\n▶ {display}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        shell=isinstance(cmd, str),
        check=check,
    )
    return result


def check_tool(name: str, install_hint: str = "") -> bool:
    if shutil.which(name):
        return True
    print(f"  ⚠ '{name}' nu a fost găsit în PATH.")
    if install_hint:
        print(f"    → {install_hint}")
    return False


# ── Steps ─────────────────────────────────────────────────────────────────────

def clean_build():
    print("\n── Curățare build anterior ──")
    for d in [BUILD_DIR, DIST_DIR, Path("__pycache__")]:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            print(f"  Șters: {d}")
    for spec_bak in Path(".").glob("*.spec.bak"):
        spec_bak.unlink(missing_ok=True)


def build_electron_display() -> bool:
    """Compilează Display Engine Electron cu @electron/packager.

    Produce un executabil standalone (fără Node.js pe client):
      build/electron-compiled/CantioDisplay-{platform}-x64/CantioDisplay[.exe]

    Fallback: dacă packager eșuează, returnează False și build-ul continuă
    cu _copy_electron_source() (copiază display-electron/ + node_modules/).
    """
    print("\n── Build Electron Display (electron-packager) ──")
    electron_dir = Path("display-electron")

    if not electron_dir.exists():
        print("  ❌ display-electron/ lipsește!")
        return False

    npm = "npm.cmd" if sys.platform == "win32" else "npm"

    # 1. npm install (include devDependencies pentru packager)
    print("  → npm install...")
    run([npm, "install"], cwd=electron_dir)

    # 2. Verifică / instalează @electron/packager ca devDependency
    if sys.platform == "win32":
        packager_bin = electron_dir / "node_modules" / ".bin" / "electron-packager.cmd"
    else:
        packager_bin = electron_dir / "node_modules" / ".bin" / "electron-packager"

    if not packager_bin.exists():
        print("  → Instalez @electron/packager...")
        run([npm, "install", "--save-dev", "@electron/packager"], cwd=electron_dir)

    if not packager_bin.exists():
        print("  ❌ electron-packager indisponibil după install!")
        return False

    # 3. Determină platforma curentă
    if sys.platform == "win32":
        plat = "win32"
    elif sys.platform == "darwin":
        plat = "darwin"
    else:
        plat = "linux"
    arch = "x64"

    # 4. Director output
    out_dir = Path("build") / "electron-compiled"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 5. Rulează electron-packager
    print(f"  → electron-packager ({plat}-{arch})...")
    packager_args = [
        str(packager_bin),
        str(electron_dir),        # sourcedir
        "CantioDisplay",          # appname
        f"--platform={plat}",
        f"--arch={arch}",
        f"--out={out_dir}",
        "--overwrite",
        "--prune=true",
        r"--ignore=\.git",
        r"--ignore=node_modules/\.cache",
        "--electron-version=28.3.0",
    ]
    if sys.platform == "win32":
        packager_args.append("--win32metadata.ProductName=CantioDisplay")

    try:
        run(packager_args)
    except subprocess.CalledProcessError as e:
        print(f"  ❌ electron-packager eșuat: {e}")
        return False

    # 6. Verifică output
    compiled_dir = out_dir / f"CantioDisplay-{plat}-{arch}"
    exe_name = "CantioDisplay.exe" if plat == "win32" else "CantioDisplay"
    exe_path = compiled_dir / exe_name

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / 1024 / 1024
        print(f"  ✅ Compilat: {exe_path} ({size_mb:.1f} MB)")
        return True
    elif compiled_dir.exists():
        print(f"  ✅ Compilat (dir): {compiled_dir}")
        return True
    else:
        print(f"  ⚠ Output dir negăsit: {compiled_dir}")
        return False


def build_python():
    """Compilează Python cu PyInstaller."""
    print("\n── Build Python (PyInstaller) ──")

    if not Path("cantio.spec").exists():
        print("  ❌ cantio.spec lipsește!")
        sys.exit(1)

    run([sys.executable, "-m", "PyInstaller", "--clean", "cantio.spec"])
    print("  ✅ Python compilat")


def copy_electron_to_dist():
    """Copiază Electron compilat (sau sursă fallback) în dist/Cantio/.

    Structura finală preferată (compilat cu electron-packager):
      dist/Cantio/
        Cantio.exe
        _internal/              ← PyInstaller
        CantioDisplay/          ← standalone, fără Node.js pe client
          CantioDisplay.exe
          resources/app/...

    Fallback (dacă compilat lipsește):
      dist/Cantio/
        display-electron/       ← necesită Node.js instalat pe client
          main.js, display.html, display.js, package.json
          node_modules/electron/, ws/, ...
    """
    print("\n── Copiere Electron Display în dist/ ──")

    if sys.platform == "win32":
        plat = "win32"
    elif sys.platform == "darwin":
        plat = "darwin"
    else:
        plat = "linux"

    compiled_src = Path("build") / "electron-compiled" / f"CantioDisplay-{plat}-x64"

    if compiled_src.exists():
        # ── Cale preferată: executabil compilat standalone ──────────────────
        dst = Path("dist/Cantio/CantioDisplay")
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(compiled_src, dst)
        print(f"  ✅ Electron compilat copiat: {compiled_src} → {dst}")

        exe_name = "CantioDisplay.exe" if plat == "win32" else "CantioDisplay"
        exe_path = dst / exe_name
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / 1024 / 1024
            print(f"  ✅ Executabil: {exe_path} ({size_mb:.1f} MB)")
    else:
        # ── Fallback: sursă cu node_modules ────────────────────────────────
        print("  ⚠ Executabil compilat negăsit — fallback la sursă (node_modules)")
        _copy_electron_source()


def _copy_electron_source():
    """Fallback: copiază display-electron/ cu node_modules în dist/Cantio/display-electron/.

    Necesită Node.js instalat pe mașina client (sau electron în node_modules).
    """
    src = Path("display-electron")
    dst = Path("dist/Cantio/display-electron")

    if not src.exists():
        print("  ❌ display-electron/ lipsește!")
        return

    if dst.exists():
        shutil.rmtree(dst)

    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns(
            ".cache", "*.log", "*.map",
            "electron-builder*", "__pycache__",
        ),
    )
    print(f"  ✅ Sursă Electron copiată: {src} → {dst}")

    # Verifică că executabilul electron există în node_modules/electron/dist/
    if sys.platform == "win32":
        electron_dist_bin = dst / "node_modules" / "electron" / "dist" / "electron.exe"
    else:
        electron_dist_bin = dst / "node_modules" / "electron" / "dist" / "electron"

    if electron_dist_bin.exists():
        print(f"  ✅ Electron dist bin: {electron_dist_bin}")
    else:
        print("  ⚠ Electron dist bin lipsă — încerc npm install --omit=dev ...")
        npm = "npm.cmd" if sys.platform == "win32" else "npm"
        try:
            subprocess.run([npm, "install", "--omit=dev"], cwd=str(src), check=True)
            print("  ✅ npm install finalizat!")
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(
                src, dst,
                ignore=shutil.ignore_patterns(
                    ".cache", "*.log", "*.map",
                    "electron-builder*", "__pycache__",
                ),
            )
            print(f"  ✅ Recopiat cu node_modules: {src} → {dst}")
        except Exception as e:
            print(f"  ❌ npm install eșuat: {e}")
            print("  → Rulează manual: cd display-electron && npm install")


def copy_assets():
    """Copiază assets statice în dist/Cantio/."""
    print("\n── Copiere Assets ──")

    assets = ["GProICON.png", "SplashScreen.png", "LICENSE", "README.md"]
    if os.path.exists("GPSPLASH-cutout.png"):
        assets.append("GPSPLASH-cutout.png")
    if os.path.exists("GProICON.ico"):
        assets.append("GProICON.ico")

    for asset in assets:
        if os.path.exists(asset):
            shutil.copy2(asset, "dist/Cantio/")
            print(f"  ✅ {asset}")
        else:
            print(f"  ⚠ Lipsă (skip): {asset}")

    if os.path.exists("mdbtools"):
        shutil.copytree("mdbtools", "dist/Cantio/mdbtools", dirs_exist_ok=True)
        print("  ✅ mdbtools/")


# ── Installer builders ────────────────────────────────────────────────────────

def build_installer_windows():
    """Generează script NSIS și compilează instalatorul .exe."""
    print("\n── Build Instalator Windows (NSIS) ──")

    nsis_script = r"""
; Cantio Installer — NSIS Script
; Genererat automat de build.py

!define APP_NAME "Cantio"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "Senegeac Tudor"
!define APP_URL "https://cantioapp.com"
!define APP_EXE "Cantio.exe"
!define REG_KEY "Software\Cantio"
!define UNINSTALL_KEY \
    "Software\Microsoft\Windows\CurrentVersion\Uninstall\Cantio"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "Cantio-Setup-v${APP_VERSION}-Windows.exe"
Unicode True
SetCompressor /SOLID lzma

RequestExecutionLevel admin
InstallDir "$PROGRAMFILES64\${APP_NAME}"

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Romanian"
!insertmacro MUI_LANGUAGE "English"

; ── Instalare ──────────────────────────────────────────────────────────────────
Section "Cantio" SecMain
    SectionIn RO
    ; Copiază recursiv: Cantio.exe, _internal/, CantioDisplay/ (sau display-electron/), assets
    ; File /r copiază toate subdirectoarele — CantioDisplay/ e inclus automat
    SetOutPath "$INSTDIR"
    File /r "dist\Cantio\*.*"

    ; Shortcut Desktop
    CreateShortcut \
        "$DESKTOP\Cantio.lnk" \
        "$INSTDIR\Cantio.exe" "" \
        "$INSTDIR\GProICON.ico"

    ; Shortcut Start Menu
    CreateDirectory "$SMPROGRAMS\Cantio"
    CreateShortcut \
        "$SMPROGRAMS\Cantio\Cantio.lnk" \
        "$INSTDIR\Cantio.exe" "" \
        "$INSTDIR\GProICON.ico"
    CreateShortcut \
        "$SMPROGRAMS\Cantio\Dezinstaleaza.lnk" \
        "$INSTDIR\Uninstall.exe"

    ; Registry
    WriteRegStr HKLM "${REG_KEY}" "InstallPath" "$INSTDIR"
    WriteRegStr HKLM "${REG_KEY}" "Version"     "${APP_VERSION}"

    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayName"    "${APP_NAME}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "Publisher"      "${APP_PUBLISHER}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "URLInfoAbout"   "${APP_URL}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "UninstallString" \
        "$INSTDIR\Uninstall.exe"
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify" 1
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair" 1

    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

; ── Dezinstalare ───────────────────────────────────────────────────────────────
Section "Uninstall"
    RMDir /r "$INSTDIR"
    Delete   "$DESKTOP\Cantio.lnk"
    RMDir /r "$SMPROGRAMS\Cantio"
    DeleteRegKey HKLM "${REG_KEY}"
    DeleteRegKey HKLM "${UNINSTALL_KEY}"

    ; Datele utilizator NU se șterg ($USERPROFILE\Cantio)
    MessageBox MB_OK \
        "Cantio a fost dezinstalat.$\n$\nDatele tale (cantari, setari) au fost pastrate in:$\n$PROFILE\Cantio"
SectionEnd
"""

    nsi_path = "cantio_installer.nsi"
    with open(nsi_path, 'w', encoding='utf-8') as f:
        f.write(nsis_script)
    print(f"  Script NSIS salvat: {nsi_path}")

    # Caută makensis
    nsis_locations = [
        r"C:\Program Files (x86)\NSIS\makensis.exe",
        r"C:\Program Files\NSIS\makensis.exe",
        "makensis",
    ]
    nsis_exe = next(
        (p for p in nsis_locations
         if (os.path.exists(p) if p.endswith('.exe') else shutil.which(p))),
        None,
    )

    if nsis_exe:
        run([nsis_exe, nsi_path])
        print("  ✅ Instalator Windows creat!")
    else:
        print("""
  ⚠ NSIS nu este instalat.
    Descarcă de la: https://nsis.sourceforge.io/
    Sau cu Chocolatey: choco install nsis -y
    Apoi rulează manual: makensis cantio_installer.nsi
""")


def build_installer_mac():
    """Creează DMG pentru macOS."""
    print("\n── Build DMG macOS ──")

    script = """\
#!/bin/bash
APP_NAME="Cantio"
VERSION="1.0.0"
DMG_NAME="${APP_NAME}-v${VERSION}-macOS.dmg"
APP_PATH="dist/${APP_NAME}.app"
DMG_DIR="build/dmg_temp"

mkdir -p "$DMG_DIR"
cp -r "$APP_PATH" "$DMG_DIR/"
ln -sf /Applications "$DMG_DIR/Applications"

hdiutil create \\
    -volname "${APP_NAME}" \\
    -srcfolder "$DMG_DIR" \\
    -ov -format UDZO \\
    "${DMG_NAME}"

rm -rf "$DMG_DIR"
echo "✅ DMG creat: ${DMG_NAME}"
"""
    with open("build_mac.sh", 'w') as f:
        f.write(script)
    os.chmod("build_mac.sh", 0o755)
    run(["bash", "build_mac.sh"])
    print("  ✅ DMG macOS creat!")


def build_installer_linux():
    """Creează AppImage pentru Linux."""
    print("\n── Build AppImage Linux ──")

    appdir = Path("build/Cantio.AppDir")
    appdir.mkdir(parents=True, exist_ok=True)

    (appdir / "Cantio.desktop").write_text(
        "[Desktop Entry]\n"
        "Name=Cantio\n"
        "Exec=Cantio\n"
        "Icon=cantio\n"
        "Type=Application\n"
        "Categories=AudioVideo;Music;\n"
        "Comment=Software prezentare versuri\n"
    )

    usr_bin = appdir / "usr" / "bin" / "Cantio"
    if Path("dist/Cantio").exists():
        shutil.copytree("dist/Cantio", str(usr_bin), dirs_exist_ok=True)

    if Path("GProICON.png").exists():
        shutil.copy2("GProICON.png", str(appdir / "cantio.png"))

    apprun = appdir / "AppRun"
    apprun.write_text(
        '#!/bin/bash\n'
        'APPDIR="$(dirname "$(readlink -f "$0")")"\n'
        'exec "$APPDIR/usr/bin/Cantio/Cantio" "$@"\n'
    )
    apprun.chmod(0o755)

    if not shutil.which("appimagetool"):
        print("""
  ⚠ appimagetool nu este instalat!
    Descarcă de la: https://github.com/AppImage/AppImageKit/releases
    Sau: pip install appimage-builder
""")
        return

    run(["appimagetool", str(appdir), "Cantio-v1.0.0-Linux.AppImage"])
    print("  ✅ AppImage Linux creat!")


# ── Icon helper ───────────────────────────────────────────────────────────────

def ensure_icon_ico():
    """Convertește GProICON.png → GProICON.ico dacă .ico lipsește."""
    if os.path.exists("GProICON.ico"):
        return
    if not os.path.exists("GProICON.png"):
        print("  ⚠ GProICON.png lipsește — icon lipsă!")
        return
    try:
        from PIL import Image
        img = Image.open("GProICON.png")
        img.save("GProICON.ico", format="ICO",
                 sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
        print("  ✅ GProICON.ico generat din PNG")
    except ImportError:
        print("  ⚠ Pillow lipsă — GProICON.ico nu a fost generat")
        print("    → pip install Pillow")
    except Exception as e:
        print(f"  ⚠ Conversie icon eșuată: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("CANTIO BUILD SYSTEM v1.0.0")
    print(f"Platformă: {platform.system()} {platform.machine()}")
    print(f"Python: {sys.version.split()[0]}")
    print("=" * 60)

    if not os.path.exists("main.py"):
        print("❌ Rulează build.py din folderul C:\\Cantio\\!")
        sys.exit(1)

    # Verifică PyInstaller
    print("\n── Verificare dependințe ──")
    try:
        import PyInstaller
        print(f"  ✅ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("  ❌ PyInstaller lipsă! → pip install pyinstaller")
        sys.exit(1)

    # Verifică Node / npm
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    if shutil.which(npm) or shutil.which("npm"):
        import subprocess as _sp
        try:
            ver = _sp.check_output([npm, "--version"], text=True).strip()
            print(f"  ✅ npm {ver}")
        except Exception:
            print("  ✅ npm găsit")
    else:
        print("  ⚠ npm negăsit — build Electron va eșua")

    # Alege acțiunea
    if len(sys.argv) > 1:
        action = sys.argv[1].lower()
    else:
        print("""
Ce vrei să buildezi?
  1. Build complet (recomandat)
  2. Doar Python (PyInstaller)
  3. Doar Electron Display
  4. Doar Instalator
  5. Clean și rebuild total
""")
        choice = input("Alegere (1-5, default=1): ").strip() or "1"
        action = {'1':'all','2':'python','3':'electron',
                  '4':'installer','5':'clean'}.get(choice, 'all')

    if action == 'clean':
        clean_build()
        action = 'all'

    # Generează icon .ico dacă lipsește (necesar pe Windows)
    if sys.platform == "win32":
        ensure_icon_ico()

    if action in ('all', 'electron'):
        build_electron_display()

    if action in ('all', 'python'):
        build_python()
        copy_electron_to_dist()
        copy_assets()

    if action in ('all', 'installer'):
        if sys.platform == 'win32':
            build_installer_windows()
        elif sys.platform == 'darwin':
            build_installer_mac()
        else:
            build_installer_linux()

    print("\n" + "=" * 60)
    print("✅ BUILD COMPLET!")
    print("=" * 60)

    # Listează ce s-a creat
    print("\nFișiere create:")
    patterns = {
        'win32':  "Cantio-Setup-*.exe",
        'darwin': "Cantio-*-macOS.dmg",
    }
    pat = patterns.get(sys.platform, "Cantio-*-Linux.AppImage")
    found = list(Path(".").glob(pat))
    if found:
        for f in found:
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"  📦 {f} ({size_mb:.1f} MB)")
    else:
        dist = Path("dist/Cantio")
        if dist.exists():
            print(f"  📁 dist/Cantio/ (instalator negenerat)")


if __name__ == "__main__":
    main()
