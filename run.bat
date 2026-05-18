@echo off
cd /d "%~dp0"
call .env 2>nul
python login.py
pause
