@echo off
echo Building Chotto Voice...

REM Activate virtual environment if exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate
)

REM Install pyinstaller if not installed
pip install pyinstaller

REM Build exe using spec file
pyinstaller --clean build.spec

echo.
echo Build complete! Check dist\ChottoVoice.exe
pause
