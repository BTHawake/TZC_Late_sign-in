@echo off
chcp 65001 >nul
cd /d "%~dp0"

set CMD=cmd /c cd /d %CD% ^&^& python login.py
schtasks /create /tn TZC_auto_checkin /tr "%CMD%" /sc daily /st 21:30 /it /f
if %errorlevel%==0 (echo Task created: TZC_auto_checkin) else (echo FAILED - run as Administrator!)
pause
