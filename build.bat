@echo off
echo ================================================
echo   GlorifyPro - Build Script
echo ================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from python.org
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
pip install PyQt6 pyinstaller python-docx pymupdf sqlalchemy lxml flask Pillow

echo.
echo Converting PNG icon to ICO...
python -c "from PIL import Image; img = Image.open('GlorifyPro_icon.png'); img.save('GlorifyPro.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(256,256)])"
if errorlevel 1 (
    echo WARNING: Could not create GlorifyPro.ico. Build will continue without icon.
)

echo.
echo Building GlorifyPro.exe...
pyinstaller GlorifyPro.spec --clean

echo.
if exist "dist\GlorifyPro.exe" (
    echo ================================================
    echo   SUCCESS! GlorifyPro.exe is in the dist folder
    echo ================================================
) else (
    echo Build failed. Check errors above.
)
pause
