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
    from src.user_config import WHISPER_LOCAL, WHISPER_OPENAI_API

    openai_key = user_config.openai_api_key or settings.openai_api_key
    whisper_provider = user_config.whisper_provider

    try:
        if whisper_provider == WHISPER_OPENAI_API and openai_key:
            print("Using OpenAI Whisper API")
            return create_transcriber(
                provider=WHISPER_OPENAI_API,
                api_key=openai_key,
                model="whisper-1",
            )
        if whisper_provider == WHISPER_OPENAI_API:
            print("Warning: Whisper API selected but no OpenAI key; using local")
        return create_transcriber(
            provider=WHISPER_LOCAL,
            model=user_config.whisper_local_model,
        )
    except Exception as e:
        print(f"Warning: Transcriber error: {e}")
        print("音声認識が利用できません。")
        return None


def _provider_is_ready(spec, creds) -> bool:
    """Whether a provider has enough configuration to be usable."""
    if spec.needs_api_key and not creds["api_key"]:
        return False
    if spec.needs_base_url and not (creds["base_url"] or spec.default_base_url):
        return False
    return True


def create_ai_client_from_config(user_config, settings):
    """Create an AI client for the user's selected provider.

    Tries the explicitly selected provider first, then falls back to any other
    provider that has sufficient configuration.
    """
    from src.ai_client import PROVIDERS

    ordered = [user_config.ai_provider] + [
        p for p in PROVIDERS if p != user_config.ai_provider
    ]

    for provider in ordered:
        spec = PROVIDERS.get(provider)
        if spec is None:
            continue
        creds = user_config.credentials_for(provider)
        if not _provider_is_ready(spec, creds):
            continue
        try:
            client = create_ai_client(
                provider=provider,
                api_key=creds["api_key"],
                model=creds["model"] or None,
                base_url=creds["base_url"] or None,
            )
            print(f"Using {spec.label} for AI processing")
            return client
        except Exception as e:
            print(f"Warning: {provider} client error: {e}")

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
