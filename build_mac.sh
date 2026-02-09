#!/bin/bash
# Build Chotto Voice for macOS

set -e

echo "🎤 Building Chotto Voice for macOS..."

# Check if running on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "❌ This script must be run on macOS"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Build with PyInstaller
echo "🔨 Building application..."
pyinstaller --clean build_mac.spec

# Check if build succeeded
if [ -d "dist/ChottoVoice.app" ]; then
    echo ""
    echo "✅ Build successful!"
    echo "📂 Application: dist/ChottoVoice.app"
    echo ""
    echo "📝 Notes:"
    echo "  - First run: Grant microphone permission in System Preferences"
    echo "  - For global hotkeys: Grant accessibility permission"
    echo ""
    
    # Create DMG (optional)
    if command -v create-dmg &> /dev/null; then
        echo "📀 Creating DMG..."
        create-dmg \
            --volname "Chotto Voice" \
            --window-pos 200 120 \
            --window-size 600 400 \
            --icon-size 100 \
            --app-drop-link 450 185 \
            "dist/ChottoVoice.dmg" \
            "dist/ChottoVoice.app"
        echo "📀 DMG created: dist/ChottoVoice.dmg"
    fi
else
    echo "❌ Build failed"
    exit 1
fi
