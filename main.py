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
from src.ui.main_window import MainWindow, FirstRunSetupDialog


def create_transcriber_from_config(user_config, settings):
    """Create transcriber based on user config."""
    openai_key = user_config.openai_api_key or settings.openai_api_key
    whisper_provider = user_config.whisper_provider
    
    try:
        if whisper_provider == "local":
            transcriber = create_transcriber(
                provider="local",
                model=user_config.whisper_local_model
            )
            print(f"Using local Whisper ({user_config.whisper_local_model})")
            return transcriber
        elif openai_key:
            transcriber = create_transcriber(
                provider="openai_api",
                api_key=openai_key,
                model="whisper-1"
            )
            print("Using OpenAI Whisper API")
            return transcriber
        else:
            print("Warning: Whisper API selected but no OpenAI key provided")
            print("Falling back to local Whisper")
            transcriber = create_transcriber(
                provider="local",
                model=user_config.whisper_local_model
            )
            return transcriber
    except Exception as e:
        print(f"Warning: Transcriber error: {e}")
        print("音声認識が利用できません。")
        return None


def create_ai_client_from_config(user_config, settings):
    """Create AI client based on user config."""
    gemini_key = user_config.gemini_api_key
    anthropic_key = user_config.anthropic_api_key or settings.anthropic_api_key
    openai_key = user_config.openai_api_key or settings.openai_api_key
    
    try:
        if gemini_key:
            client = create_ai_client(
                provider="gemini",
                api_key=gemini_key,
                model="gemini-2.0-flash"
            )
            print("Using Google Gemini for AI processing")
            return client
        elif anthropic_key:
            client = create_ai_client(
                provider="claude",
                api_key=anthropic_key,
                model=settings.claude_model
            )
            print("Using Claude for AI processing")
            return client
        elif openai_key:
            client = create_ai_client(
                provider="openai",
                api_key=openai_key,
                model=settings.openai_model
            )
            print("Using OpenAI GPT for AI processing")
            return client
    except Exception as e:
        print(f"Warning: AI client error: {e}")
    
    return None


def main():
    """Main entry point."""
    # Load settings
    settings = get_settings()
    
    # Load persistent user config
    user_config = UserConfig.load()
    
    # Create and run application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray
    
    # First run setup
    if not user_config.first_run_complete:
        setup_dialog = FirstRunSetupDialog(user_config)
        result = setup_dialog.exec()
        
        # Mark first run as complete
        user_config.update(first_run_complete=True)
        
        # Reload config after setup
        user_config = UserConfig.load()
    
    # Create components
    recorder = AudioRecorder(
        sample_rate=settings.sample_rate,
        channels=settings.channels
    )
    
    # Create transcriber and AI client
    transcriber = create_transcriber_from_config(user_config, settings)
    ai_client = create_ai_client_from_config(user_config, settings)
    
    # Create hotkey config from user config (persistent settings)
    hotkey_config = HotkeyConfig(
        key=user_config.hotkey,
        double_tap_threshold=user_config.hotkey_double_tap_threshold,
        hold_threshold=user_config.hotkey_hold_threshold
    )
    
    window = MainWindow(recorder, transcriber, ai_client, hotkey_config, user_config)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
