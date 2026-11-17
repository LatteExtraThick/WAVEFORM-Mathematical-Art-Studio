@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo       WAVEFORM - Windows App Builder
echo ==========================================
py -m pip install --upgrade pip
if errorlevel 1 goto :error
py -m pip install -r requirements.txt
if errorlevel 1 goto :error
py -m pip install pyinstaller
if errorlevel 1 goto :error
py -m PyInstaller --noconfirm --clean WAVEFORM.spec
if errorlevel 1 goto :error
echo.
echo Build complete!
echo App folder: dist\WAVEFORM\
echo Run: dist\WAVEFORM\WAVEFORM.exe
echo.
echo To create a Setup.exe installer, install Inno Setup and run:
echo   ISCC.exe installer\WAVEFORM.iss
pause
exit /b 0
:error
echo.
echo BUILD FAILED. Check the error above.
pause
exit /b 1
