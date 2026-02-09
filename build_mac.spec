# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Chotto Voice (macOS)

import sys
sys.setrecursionlimit(5000)

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui', 
        'PyQt6.QtWidgets',
        'sounddevice',
        'numpy',
        'anthropic',
        'openai',
        'google.genai',
        'whisper',
        'tiktoken',
        'tiktoken_ext',
        'tiktoken_ext.openai_public',
        'keyboard',
        'pyperclip',
        'pydantic',
        'pydantic_settings',
        'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Windows-only modules
        'pycaw',
        'comtypes',
        'win32com',
        'pywin32',
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
    exclude_binaries=True,
    name='ChottoVoice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,  # macOS: handle file open events
    target_arch=None,  # Build for current arch (arm64 or x86_64)
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon.icns path here if you have one
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

app = BUNDLE(
    coll,
    name='ChottoVoice.app',
    icon=None,  # Add icon.icns path here
    bundle_identifier='com.halz.chottovoice',
    info_plist={
        'CFBundleName': 'Chotto Voice',
        'CFBundleDisplayName': 'Chotto Voice',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSMicrophoneUsageDescription': 'Chotto Voice needs microphone access for voice recording.',
        'NSAppleEventsUsageDescription': 'Chotto Voice uses AppleScript to control system volume.',
        # Accessibility required for global hotkeys
        'NSAccessibilityUsageDescription': 'Chotto Voice needs accessibility access for global hotkeys.',
        'LSUIElement': False,  # Set to True if you want menu bar only (no dock icon)
        'NSHighResolutionCapable': True,
    },
)
