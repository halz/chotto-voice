@echo off
echo ============================================
echo  Chotto Voice - Portable Build Script
echo ============================================
echo.

REM Step 1: Download models
echo [1/3] Downloading models...
python download_models.py
if errorlevel 1 (
    echo ERROR: Model download failed!
    pause
    exit /b 1
)

REM Step 2: Build with PyInstaller
echo.
echo [2/3] Building portable EXE...
pyinstaller build_portable.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: Build failed!
    pause
    exit /b 1
)

REM Step 3: Copy models to dist (if not included by spec)
echo.
echo [3/3] Verifying models in dist...
if not exist "dist\ChottoVoice\models" mkdir "dist\ChottoVoice\models"

if exist "models\Qwen3.5-0.8B-Q4_K_M.gguf" (
    if not exist "dist\ChottoVoice\models\Qwen3.5-0.8B-Q4_K_M.gguf" (
        echo Copying Qwen model...
        copy "models\Qwen3.5-0.8B-Q4_K_M.gguf" "dist\ChottoVoice\models\"
    )
)

echo.
echo ============================================
echo  BUILD COMPLETE!
echo ============================================
echo.
echo Output: dist\ChottoVoice\
echo.
echo To distribute:
echo   1. ZIP the dist\ChottoVoice\ folder
echo   2. Share the ZIP
echo   3. Users extract and run ChottoVoice.exe
echo.

REM Show size
echo Calculating size...
powershell -Command "'{0:N0} MB' -f ((Get-ChildItem -Path 'dist\ChottoVoice' -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB)"

echo.
pause
