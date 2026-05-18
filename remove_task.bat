@echo off
schtasks /delete /tn TZC_auto_checkin /f
echo 定时任务已移除
pause
