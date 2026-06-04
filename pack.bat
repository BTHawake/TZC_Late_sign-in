@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Installing dependencies...
pip install pyinstaller pillow -q

echo.
echo Converting icon...
python -c "from PIL import Image; img = Image.open('R.jpg'); img.save('app.ico', format='ICO', sizes=[(256,256)])"

echo.
echo Building tzc_checkin.exe...
pyinstaller --onefile --name tzc_checkin --icon app.ico --console login.py

echo.
echo Done! Output: dist\tzc_checkin.exe
echo.
echo Copy config.example.txt to: dist\config.txt (and edit it)
echo Delete: dist\tzc_checkin.exe.spec
pause
