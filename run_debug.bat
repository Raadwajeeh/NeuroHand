@echo off
cd /d "%~dp0"
echo Activating venv and running game...
call .venv\Scripts\activate.bat
python main.py
echo.
echo If it crashed, open crash_log.txt
pause
