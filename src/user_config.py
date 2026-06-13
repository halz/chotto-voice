"""User configuration management for Chotto Voice.

Persists user settings (hotkey, startup options) to a JSON file.
Settings are stored in the user's config directory.
"""
import json
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict, field

# Canonical Whisper provider identifiers used throughout the app.
WHISPER_LOCAL = "local"
WHISPER_OPENAI_API = "openai_api"


def get_config_dir() -> Path:
    """Get the configuration directory for the current platform."""
    if sys.platform == "win32":
        # Windows: %APPDATA%/ChottoVoice
        base = Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        # macOS: ~/Library/Application Support/ChottoVoice
        base = Path.home() / "Library" / "Application Support"
    else:
        # Linux: ~/.config/ChottoVoice
        base = Path.home() / ".config"
    
    config_dir = base / "ChottoVoice"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the path to the user config file."""
    return get_config_dir() / "settings.json"


@dataclass
class UserConfig:
    """User-configurable settings that persist across sessions."""
    
    # API Keys for the built-in cloud providers (stored here, not in .env).
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # Active AI provider (key into ai_client.PROVIDERS).
    ai_provider: str = "gemini"

    # Per-provider overrides: {provider_key: {"api_key", "base_url", "model"}}.
    # Used for model overrides and for OpenAI-compatible servers (Ollama,
    # LM Studio, generic) which need a base URL and optional API key.
    ai_settings: dict = field(default_factory=dict)

    # Whisper settings. whisper_provider is one of WHISPER_LOCAL / WHISPER_OPENAI_API.
    whisper_provider: str = WHISPER_LOCAL  # default to free local transcription
    whisper_local_model: str = "small"  # tiny, base, small, medium, large
    
    # Hotkey settings
    hotkey: str = "ctrl+shift+space"
    hotkey_double_tap_threshold: float = 0.3
    hotkey_hold_threshold: float = 0.2
    
    # UI settings
    auto_type: bool = True
    process_with_ai: bool = True
    
    # Overlay settings
    # Positions: top-left, top-center, top-right, bottom-left, bottom-center, bottom-right
    overlay_position: str = "bottom-right"
    
    # Startup settings
    start_with_windows: bool = False
    start_minimized: bool = True
    
    # First run flag
    first_run_complete: bool = False
    
    @classmethod
    def load(cls) -> "UserConfig":
        """Load config from file, or return defaults."""
        config_path = get_config_path()

        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                config = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
                config._migrate()
                return config
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Config load error: {e}, using defaults")

        return cls()

    def _migrate(self):
        """Normalise values written by older versions of the app."""
        # Older builds stored the Whisper provider as "api"; standardise it.
        if self.whisper_provider == "api":
            self.whisper_provider = WHISPER_OPENAI_API
        elif self.whisper_provider not in (WHISPER_LOCAL, WHISPER_OPENAI_API):
            self.whisper_provider = WHISPER_LOCAL

    def get_provider_settings(self, provider: str) -> dict:
        """Return the stored {api_key, base_url, model} for a provider."""
        return dict(self.ai_settings.get(provider, {}))

    def set_provider_settings(self, provider: str, **values):
        """Persist per-provider settings (only non-None values)."""
        current = dict(self.ai_settings.get(provider, {}))
        for key, value in values.items():
            if value is not None:
                current[key] = value
        self.ai_settings[provider] = current
        self.save()

    def credentials_for(self, provider: str) -> dict:
        """Return {api_key, base_url, model} for any provider.

        Bridges the three legacy top-level API-key fields (gemini/anthropic/
        openai) with the generic per-provider ``ai_settings`` store.
        """
        settings = self.ai_settings.get(provider, {})
        legacy_key = {
            "gemini": self.gemini_api_key,
            "claude": self.anthropic_api_key,
            "openai": self.openai_api_key,
        }.get(provider, "")
        return {
            "api_key": settings.get("api_key") or legacy_key,
            "base_url": settings.get("base_url", ""),
            "model": settings.get("model", ""),
        }

    def resolve_ai(self) -> dict:
        """Resolve the active provider into {provider, api_key, base_url, model}."""
        creds = self.credentials_for(self.ai_provider)
        creds["provider"] = self.ai_provider
        return creds
    
    def save(self):
        """Save config to file."""
        config_path = get_config_path()
        
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Config save error: {e}")
    
    def update(self, **kwargs):
        """Update specific fields and save."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.save()


def get_startup_folder() -> Optional[Path]:
    """Get the Windows Startup folder path."""
    if sys.platform != "win32":
        return None
    
    # Windows Startup folder: shell:startup
    startup = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return startup if startup.exists() else None


def get_shortcut_path() -> Optional[Path]:
    """Get the path to the startup shortcut."""
    startup = get_startup_folder()
    if startup:
        return startup / "Chotto Voice.lnk"
    return None


def is_startup_enabled() -> bool:
    """Check if Windows startup is enabled."""
    shortcut = get_shortcut_path()
    if not shortcut:
        return False
    
    # Check for .lnk shortcut
    if shortcut.exists():
        return True
    
    # Check for .bat fallback
    bat_path = shortcut.with_suffix(".bat")
    if bat_path.exists():
        return True
    
    return False


def enable_startup(exe_path: Optional[str] = None) -> bool:
    """Enable Windows startup by creating a shortcut.
    
    Args:
        exe_path: Path to the executable. If None, uses sys.executable.
    
    Returns:
        True if successful, False otherwise.
    """
    if sys.platform != "win32":
        return False
    
    shortcut_path = get_shortcut_path()
    if not shortcut_path:
        return False
    
    try:
        import winshell
        from win32com.client import Dispatch
        
        # Determine the target executable
        if exe_path:
            target = exe_path
        elif getattr(sys, 'frozen', False):
            # Running as compiled exe
            target = sys.executable
        else:
            # Running as script - create a batch file to run it
            target = sys.executable
            # For script mode, we need to create a different approach
            # Just point to python.exe with the script as argument
            script_path = str(Path(__file__).parent.parent / "main.py")
            
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(str(shortcut_path))
            shortcut.Targetpath = target
            shortcut.Arguments = f'"{script_path}"'
            shortcut.WorkingDirectory = str(Path(__file__).parent.parent)
            shortcut.IconLocation = target
            shortcut.Description = "Chotto Voice - 音声入力アシスタント"
            shortcut.save()
            return True
        
        # For frozen exe
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.Targetpath = target
        shortcut.WorkingDirectory = str(Path(target).parent)
        shortcut.IconLocation = target
        shortcut.Description = "Chotto Voice - 音声入力アシスタント"
        shortcut.save()
        return True
        
    except ImportError:
        # Fallback: create a simple .bat file instead
        try:
            bat_path = shortcut_path.with_suffix(".bat")
            if getattr(sys, 'frozen', False):
                content = f'@echo off\nstart "" "{sys.executable}"'
            else:
                script_path = Path(__file__).parent.parent / "main.py"
                content = f'@echo off\ncd /d "{script_path.parent}"\nstart "" pythonw "{script_path}"'
            
            with open(bat_path, "w") as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Startup enable error: {e}")
            return False
    except Exception as e:
        print(f"Startup enable error: {e}")
        return False


def disable_startup() -> bool:
    """Disable Windows startup by removing the shortcut."""
    if sys.platform != "win32":
        return False
    
    try:
        # Remove .lnk shortcut
        shortcut = get_shortcut_path()
        if shortcut and shortcut.exists():
            shortcut.unlink()
        
        # Also remove .bat if it exists
        bat_path = shortcut.with_suffix(".bat") if shortcut else None
        if bat_path and bat_path.exists():
            bat_path.unlink()
        
        return True
    except Exception as e:
        print(f"Startup disable error: {e}")
        return False


def set_startup_enabled(enabled: bool, exe_path: Optional[str] = None) -> bool:
    """Set Windows startup enabled/disabled."""
    if enabled:
        return enable_startup(exe_path)
    else:
        return disable_startup()
