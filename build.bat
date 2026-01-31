@echo off
echo Building Chotto Voice...

REM Activate virtual environment
call venv\Scripts\activate

REM Install pyinstaller if not installed
pip install pyinstaller

REM Build exe
pyinstaller --onefile --noconsole --name ChottoVoice main.py

echo.
echo Build complete! Check dist\ChottoVoice.exe
pause
