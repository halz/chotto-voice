"""Configuration management for Chotto Voice."""
from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # API Keys
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    
    # AI Provider Settings
    ai_provider: Literal["claude", "openai"] = "claude"
    claude_model: str = "claude-sonnet-4-20250514"
    openai_model: str = "gpt-4o"
    
    # Whisper Settings
    whisper_provider: Literal["openai_api", "local"] = "openai_api"
    whisper_model: str = "whisper-1"  # For API
    whisper_local_model: str = "base"  # For local: tiny, base, small, medium, large
    
    # Audio Settings
    sample_rate: int = 16000
    channels: int = 1
    
    # UI Settings
    language: Literal["ja", "en"] = "ja"
    start_minimized: bool = True  # Start in system tray by default
    
    # Hotkey Settings
    hotkey: str = "ctrl+shift+space"
    hotkey_double_tap_threshold: float = 0.3
    hotkey_hold_threshold: float = 0.2
    
    # Future: Ollama/LM Studio
    ollama_base_url: str = "http://localhost:11434"
    lm_studio_base_url: str = "http://localhost:1234/v1"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
