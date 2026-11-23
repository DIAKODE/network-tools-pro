@echo off
title Build Network Tools Pro
echo ============================================
echo   Building Network Tools Pro
echo ============================================

if exist "app_icon.ico" goto clean
echo [*] Generating app_icon.ico...
python -c "from ui.graphics import build_pulse_icon; build_pulse_icon((0, 210, 255), 256).save('app_icon.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

:clean
echo [*] Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "Network Tools Pro.spec" del /f /q "Network Tools Pro.spec"

echo [*] Compiling single-file executable...
python -m PyInstaller --noconsole --onefile --icon=app_icon.ico --name "Network Tools Pro" main.py

if not exist "dist\Network Tools Pro.exe" goto failed

echo.
echo [+] Build successful: dist\Network Tools Pro.exe
echo [*] SHA256 Checksum:
certutil -hashfile "dist\Network Tools Pro.exe" SHA256
echo.
pause
exit /b 0

:failed
echo.
echo [!] Build failed. Check the error messages above.
echo.
pause
exit /b 1