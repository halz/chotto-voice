#!/usr/bin/env python3
"""Chotto Voice - Voice input assistant application.

Supports two modes:
1. Online mode (default): Server-side transcription with Google OAuth
2. Offline mode: Local transcription for development
"""
import sys
from PyQt6.QtWidgets import QApplication

from src.config import get_settings
from src.audio import AudioRecorder
from src.transcriber import create_transcriber
from src.ai_client import create_ai_client
from src.hotkey import HotkeyConfig
from src.user_config import UserConfig
from src.api_client import ChottoVoiceAPI


def create_transcriber_from_config(user_config, settings):
    """Create transcriber based on user config (offline mode only)."""
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
    """Create AI client based on user config (offline mode only)."""
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


def run_online_mode(app, user_config, settings):
    """Run in online mode with server-side transcription."""
    from src.ui.login_dialog import LoginDialog
    from src.ui.main_window import MainWindow
    
    # Create API client
    api = ChottoVoiceAPI(server_url=user_config.server_url)
    
    # Check for existing session
    if user_config.access_token:
        try:
            api.login_with_token(user_config.access_token)
            print(f"Restored session for {api.session.email}")
        except Exception as e:
            print(f"Session expired or invalid: {e}")
            user_config.clear_login()
    
    # Show login if not authenticated
    if not api.is_authenticated:
        login_dialog = LoginDialog(api, allow_offline=True)
        result = login_dialog.exec()
        
        if login_dialog.session:
            # Save credentials
            user_config.set_login(
                access_token=login_dialog.session.access_token,
                user_id=login_dialog.session.user_id,
                email=login_dialog.session.email,
                name=login_dialog.session.name or ""
            )
        else:
            # User chose offline mode
            print("Switching to offline mode")
            return run_offline_mode(app, user_config, settings)
    
    # Create components for online mode
    recorder = AudioRecorder(
        sample_rate=settings.sample_rate,
        channels=settings.channels
    )
    
    hotkey_config = HotkeyConfig(
        key=user_config.hotkey,
        double_tap_threshold=user_config.hotkey_double_tap_threshold,
        hold_threshold=user_config.hotkey_hold_threshold
    )
    
    # Create server transcriber wrapper
    transcriber = ServerTranscriber(api)
    
    # AI processing is done server-side, but we can add local AI too
    ai_client = None  # Server handles AI processing
    
    window = MainWindow(
        recorder, transcriber, ai_client, hotkey_config, user_config,
        api=api  # Pass API for account management
    )
    
    return app.exec()


def run_offline_mode(app, user_config, settings):
    """Run in offline mode with local transcription."""
    from src.ui.main_window import MainWindow, FirstRunSetupDialog
    
    # First run setup for offline mode
    if not user_config.first_run_complete and user_config.offline_mode:
        setup_dialog = FirstRunSetupDialog(user_config)
        setup_dialog.exec()
        user_config.update(first_run_complete=True)
        user_config = UserConfig.load()
    
    # Create components
    recorder = AudioRecorder(
        sample_rate=settings.sample_rate,
        channels=settings.channels
    )
    
    transcriber = create_transcriber_from_config(user_config, settings)
    ai_client = create_ai_client_from_config(user_config, settings)
    
    hotkey_config = HotkeyConfig(
        key=user_config.hotkey,
        double_tap_threshold=user_config.hotkey_double_tap_threshold,
        hold_threshold=user_config.hotkey_hold_threshold
    )
    
    window = MainWindow(recorder, transcriber, ai_client, hotkey_config, user_config)
    
    return app.exec()


class ServerTranscriber:
    """Transcriber that uses server API."""
    
    def __init__(self, api: ChottoVoiceAPI):
        self.api = api
    
    def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio via server."""
        try:
            result = self.api.transcribe(audio_data)
            return result.get("text", "")
        except Exception as e:
            print(f"Server transcription error: {e}")
            raise


def main():
    """Main entry point."""
    # Load settings
    settings = get_settings()
    
    # Load persistent user config
    user_config = UserConfig.load()
    
    # Create application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray
    
    # Choose mode
    if user_config.offline_mode:
        # Explicit offline mode (development)
        print("Running in offline mode (development)")
        sys.exit(run_offline_mode(app, user_config, settings))
    else:
        # Default: online mode with server
        print("Running in online mode")
        sys.exit(run_online_mode(app, user_config, settings))


if __name__ == "__main__":
    main()
