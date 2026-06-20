@echo off
chcp 65001 >nul
cd /d "%~dp0"

where ffplay >nul 2>nul
if not exist "%~dp0ffplay.exe" if not exist "%~dp0ffmpeg\bin\ffplay.exe" if errorlevel 1 (
    echo ffplay.exe was not found.
    echo Put ffplay.exe in this folder or ffmpeg\bin, or add ffplay to PATH.
    echo Without ffplay, movie audio will not play.
    echo.
)

python main.py
pause
