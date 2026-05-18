@echo off
:: 注册定时任务前请先确认 .env 文件已配置正确
cd /d "%~dp0"

:: 将 .env 变量注入到任务中
for /f "tokens=1,2 delims==" %%a in (.env) do (
    set %%a=%%b
)

schtasks /create /tn TZC_auto_checkin ^
    /tr "cmd /c \"cd /d %CD% && call .env && python login.py\"" ^
    /sc daily /st 21:30 /it /f

echo 任务已创建: TZC_auto_checkin
echo 每天 21:30 自动运行
echo.
echo 检查: taskschd.msc
pause
