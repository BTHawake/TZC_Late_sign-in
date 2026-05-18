@echo off
:: 注册定时任务前请确认 config.py 已配置正确
cd /d "%~dp0"

schtasks /create /tn TZC_auto_checkin ^
    /tr "cmd /c \"cd /d %CD% && python login.py\"" ^
    /sc daily /st 21:30 /it /f

echo 任务已创建: TZC_auto_checkin
echo 每天 21:30 自动运行
echo.
echo 检查: taskschd.msc
pause
