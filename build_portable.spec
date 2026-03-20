# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Chotto Voice Portable (Windows folder build).

Usage:
    pyinstaller build_portable.spec

Output:
    dist/ChottoVoice/
        ChottoVoice.exe
        models/
            Qwen3.5-0.8B-Q4_K_M.gguf
            whisper-small/
        ... (DLLs, etc)
"""
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# === Paths ===
BASE_DIR = os.path.dirname(os.path.abspath(SPEC))
MODELS_DIR = os.path.join(BASE_DIR, 'models')

# === Data files to include ===
datas = []

# Qwen GGUF model
qwen_model = os.path.join(MODELS_DIR, 'Qwen3.5-0.8B-Q4_K_M.gguf')
if os.path.exists(qwen_model):
    datas.append((qwen_model, 'models'))
    print(f"[BUILD] Including Qwen model: {qwen_model}")
else:
    print(f"[BUILD] WARNING: Qwen model not found at {qwen_model}")
    print(f"[BUILD] Download it first: python download_models.py")

# Whisper model (small) - cached by openai-whisper
whisper_cache = os.path.join(Path.home(), '.cache', 'whisper')
if os.path.exists(whisper_cache):
    for f in os.listdir(whisper_cache):
        if 'small' in f and f.endswith('.pt'):
            src = os.path.join(whisper_cache, f)
            datas.append((src, 'models/whisper'))
            print(f"[BUILD] Including Whisper model: {f}")

# === Collect llama-cpp-python shared libs ===
llama_libs = collect_dynamic_libs('llama_cpp')
llama_datas = collect_data_files('llama_cpp')

# === Analysis ===
a = Analysis(
    ['main.py'],
    pathex=[BASE_DIR],
    binaries=llama_libs,
    datas=datas + llama_datas,
    hiddenimports=[
        'llama_cpp',
        'whisper',
        'sounddevice',
        'numpy',
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'keyboard',
        'pyperclip',
        'pydantic',
        'pydantic_settings',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude API clients we don't need for offline mode
        'anthropic',
        'openai',
        'google',
        'google.genai',
        # Exclude heavy unused packages
        'matplotlib',
        'scipy',
        'pandas',
        'PIL',
        'tkinter',
        'unittest',
        'test',
        'xmlrpc',
        'email',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # Folder mode (not onefile)
    name='ChottoVoice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=None,  # TODO: Add app icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ChottoVoice',
)
