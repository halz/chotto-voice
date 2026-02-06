#!/usr/bin/env python3
"""Chotto Voice - Voice input assistant application."""
import sys
from PyQt6.QtWidgets import QApplication

from src.config import get_settings
from src.audio import AudioRecorder
from src.transcriber import create_transcriber
from src.ai_client import create_ai_client
from src.hotkey import HotkeyConfig
from src.user_config import UserConfig
from src.ui.main_window import MainWindow


def main():
    """Main entry point."""
    # Load settings
    settings = get_settings()
    
    # Load persistent user config
    user_config = UserConfig.load()
    
    # Create components
    recorder = AudioRecorder(
        sample_rate=settings.sample_rate,
        channels=settings.channels
    )
    
    # Get API keys (user_config takes priority over .env)
    openai_key = user_config.openai_api_key or settings.openai_api_key
    anthropic_key = user_config.anthropic_api_key or settings.anthropic_api_key
    
    # Create transcriber
    transcriber = None
    try:
        if openai_key:
            transcriber = create_transcriber(
                provider=settings.whisper_provider,
                api_key=openai_key,
                model=settings.whisper_model if settings.whisper_provider == "openai_api" 
                      else settings.whisper_local_model
            )
    except ValueError as e:
        print(f"Warning: {e}")
        print("音声認識が利用できません。設定でAPIキーを確認してください。")
    
    # Create AI client
    ai_client = None
    try:
        if settings.ai_provider == "claude" and anthropic_key:
            ai_client = create_ai_client(
                provider="claude",
                api_key=anthropic_key,
                model=settings.claude_model
            )
        elif settings.ai_provider == "openai" and openai_key:
            ai_client = create_ai_client(
                provider="openai",
                api_key=openai_key,
                model=settings.openai_model
            )
    except Exception as e:
        print(f"Warning: AI client error: {e}")
    
    # Create hotkey config from user config (persistent settings)
    hotkey_config = HotkeyConfig(
        key=user_config.hotkey,
        double_tap_threshold=user_config.hotkey_double_tap_threshold,
        hold_threshold=user_config.hotkey_hold_threshold
    )
    
    # Create and run application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray
    
    window = MainWindow(recorder, transcriber, ai_client, hotkey_config, user_config)
    
    # Start minimized to tray by default
    if user_config.start_minimized:
        # Just don't show the window
        pass
    else:
        # For debugging/first run, can show window
        # window.show()
        pass
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
