@echo off
title AGE - MY BEST FRIEND AI
cd /d "%~dp0"

echo ===================================================
echo       AGE - MY BEST FRIEND AI (External Launcher)
echo ===================================================
echo.

:: 1. Check if AGE Core Server is already running on port 8765
netstat -ano | findstr ":8765" | findstr "LISTENING" >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo [OK] External AGE Core Server is already running on port 8765.
) else (
    echo [*] Starting AGE Core Engine in separate external process...
    start "" ".venv\Scripts\pythonw.exe" -m core.server.runner
    ping -n 3 127.0.0.1 >nul
    netstat -ano | findstr ":8765" | findstr "LISTENING" >nul 2>&1
    if not "%ERRORLEVEL%"=="0" (
        start "" /min ".venv\Scripts\python.exe" -m core.server.runner
        ping -n 3 127.0.0.1 >nul
    )
)

:: 3. Read session token from data\sessions\session.token if present
set TOKEN=
if exist "data\sessions\session.token" (
    set /p TOKEN=<"data\sessions\session.token"
)

set APP_URL=http://127.0.0.1:8765/
if not "%TOKEN%"=="" (
    set APP_URL=http://127.0.0.1:8765/?token=%TOKEN%
)

echo.
echo [*] Opening AGE Desktop Application Window...

:: 4. Launch in Chrome App Window (external borderless standalone app)
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app="%APP_URL%" --window-size=1120,780
    goto done
)

:: Fallback to Microsoft Edge App Window
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app="%APP_URL%" --window-size=1120,780
    goto done
)

if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files\Microsoft\Edge\Application\msedge.exe" --app="%APP_URL%" --window-size=1120,780
    goto done
)

:: Fallback to default browser
start "" "%APP_URL%"

:done
echo.
echo ===================================================
echo [SUCCESS] AGE Assistant is running externally!
echo - Global Hotkey: Press Ctrl+Space anywhere to speak
echo ===================================================
ping -n 3 127.0.0.1 >nul
exit
