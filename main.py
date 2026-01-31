#!/usr/bin/env python3
"""Chotto Voice - Voice input assistant application."""
import sys
from PyQt6.QtWidgets import QApplication

from src.config import get_settings
from src.audio import AudioRecorder
from src.transcriber import create_transcriber
from src.ai_client import create_ai_client
from src.hotkey import HotkeyConfig
from src.ui.main_window import MainWindow


def main():
    """Main entry point."""
    # Load settings
    settings = get_settings()
    
    # Create components
    recorder = AudioRecorder(
        sample_rate=settings.sample_rate,
        channels=settings.channels
    )
    
    # Create transcriber
    transcriber = create_transcriber(
        provider=settings.whisper_provider,
        api_key=settings.openai_api_key,
        model=settings.whisper_model if settings.whisper_provider == "openai_api" 
              else settings.whisper_local_model
    )
    
    # Create AI client
    ai_client = None
    if settings.ai_provider == "claude" and settings.anthropic_api_key:
        ai_client = create_ai_client(
            provider="claude",
            api_key=settings.anthropic_api_key,
            model=settings.claude_model
        )
    elif settings.ai_provider == "openai" and settings.openai_api_key:
        ai_client = create_ai_client(
            provider="openai",
            api_key=settings.openai_api_key,
            model=settings.openai_model
        )
    
    # Create hotkey config
    hotkey_config = HotkeyConfig(
        key=settings.hotkey,
        double_tap_threshold=settings.hotkey_double_tap_threshold,
        hold_threshold=settings.hotkey_hold_threshold
    )
    
    # Create and run application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray
    
    window = MainWindow(recorder, transcriber, ai_client, hotkey_config)
    
    if not settings.start_minimized:
        window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
