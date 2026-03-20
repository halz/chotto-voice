#!/usr/bin/env python3
"""Download models for Chotto Voice portable build.

Run this before building the portable EXE:
    python download_models.py
    pyinstaller build_portable.spec

Downloads:
    - Qwen3.5-0.8B Q4_K_M GGUF (~500MB)
    - Whisper small model (~244MB)
"""
import os
import sys
import urllib.request
from pathlib import Path


MODELS_DIR = Path(__file__).parent / "models"


def download_with_progress(url: str, dest: str, name: str):
    """Download a file with progress display."""
    if os.path.exists(dest):
        size_mb = os.path.getsize(dest) / (1024 * 1024)
        print(f"  ✅ {name} already exists ({size_mb:.0f} MB)")
        return
    
    print(f"  ⏳ Downloading {name}...")
    
    def progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(downloaded * 100 / total_size, 100)
            mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            bar = "█" * int(pct // 2) + "░" * (50 - int(pct // 2))
            print(f"\r  {bar} {pct:.0f}% ({mb:.0f}/{total_mb:.0f} MB)", end="", flush=True)
    
    try:
        urllib.request.urlretrieve(url, dest, reporthook=progress)
        print(f"\n  ✅ {name} downloaded!")
    except Exception as e:
        if os.path.exists(dest):
            os.remove(dest)
        print(f"\n  ❌ Failed: {e}")
        sys.exit(1)


def download_qwen():
    """Download Qwen3.5-0.8B GGUF model."""
    print("\n📦 Qwen3.5-0.8B (Q4_K_M)")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    
    url = "https://huggingface.co/Qwen/Qwen3.5-0.8B-GGUF/resolve/main/qwen3.5-0.8b-q4_k_m.gguf"
    dest = str(MODELS_DIR / "Qwen3.5-0.8B-Q4_K_M.gguf")
    download_with_progress(url, dest, "Qwen3.5-0.8B Q4_K_M")


def download_whisper():
    """Download Whisper small model."""
    print("\n📦 Whisper (small)")
    
    # Whisper downloads to ~/.cache/whisper/ by default
    # We'll trigger the download via whisper's built-in downloader
    try:
        import whisper
        print("  ⏳ Loading Whisper small model (will download if needed)...")
        whisper.load_model("small", download_root=str(MODELS_DIR / "whisper"))
        print("  ✅ Whisper small model ready!")
    except ImportError:
        print("  ⚠️ whisper not installed. Install with: pip install openai-whisper")
        print("  Whisper model will be downloaded on first run instead.")


def main():
    print("=" * 60)
    print("🎤 Chotto Voice - Model Downloader")
    print("=" * 60)
    
    download_qwen()
    download_whisper()
    
    print("\n" + "=" * 60)
    total_size = 0
    for f in MODELS_DIR.rglob("*"):
        if f.is_file():
            total_size += f.stat().st_size
    print(f"📁 Models directory: {MODELS_DIR}")
    print(f"📏 Total size: {total_size / (1024*1024):.0f} MB")
    print(f"\n🔨 Next step: pyinstaller build_portable.spec")
    print("=" * 60)


if __name__ == "__main__":
    main()
