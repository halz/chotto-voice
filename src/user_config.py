"""User configuration management for Chotto Voice.

Persists user settings (hotkey, startup options) to a JSON file.
Settings are stored in the user's config directory.

NOTE: API keys are NOT stored locally in production mode.
Only the server access token is stored after Google OAuth login.
"""
import json
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict, field


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
    
    # === Authentication (Server Mode) ===
    # Access token from server after Google OAuth login
    access_token: str = ""
    user_email: str = ""
    user_name: str = ""
    user_id: str = ""
    
    # Server URL (can be overridden for dev/staging)
    server_url: str = "https://api.chotto.voice"
    
    # === Offline Mode (Development Only) ===
    # These are only used when offline_mode=True
    # In production, transcription goes through the server
    offline_mode: bool = False
    offline_openai_key: str = ""  # Only for offline dev
    offline_gemini_key: str = ""  # Only for offline dev
    offline_anthropic_key: str = ""  # Only for offline dev
    
    # Whisper settings (offline mode only)
    whisper_provider: str = "local"  # "local" or "api"
    whisper_local_model: str = "small"  # tiny, base, small, medium, large
    
    # === Hotkey settings ===
    hotkey: str = "ctrl+shift+space"
    hotkey_double_tap_threshold: float = 0.3
    hotkey_hold_threshold: float = 0.2
    
    # === UI settings ===
    auto_type: bool = True
    process_with_ai: bool = True
    
    # Overlay settings
    # Positions: top-left, top-center, top-right, bottom-left, bottom-center, bottom-right
    overlay_position: str = "bottom-right"
    
    # === Startup settings ===
    start_with_windows: bool = False
    start_minimized: bool = True
    
    # First run flag
    first_run_complete: bool = False
    
    @property
    def is_logged_in(self) -> bool:
        """Check if user is logged in (has access token)."""
        return bool(self.access_token)
    
    @classmethod
    def load(cls) -> "UserConfig":
        """Load config from file, or return defaults."""
        config_path = get_config_path()
        
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Config load error: {e}, using defaults")
        
        return cls()
    
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
    
    def set_login(self, access_token: str, user_id: str, email: str, name: str = ""):
        """Set login credentials after successful OAuth."""
        self.access_token = access_token
        self.user_id = user_id
        self.user_email = email
        self.user_name = name
        self.save()
    
    def clear_login(self):
        """Clear login credentials (logout)."""
        self.access_token = ""
        self.user_id = ""
        self.user_email = ""
        self.user_name = ""
        self.save()
    
    # === Legacy API key properties (for backward compatibility) ===
    # These redirect to offline_ versions and warn if used in production
    
    @property
    def openai_api_key(self) -> str:
        """Get OpenAI API key (offline mode only)."""
        if not self.offline_mode:
            return ""  # Don't expose in production mode
        return self.offline_openai_key
    
    @openai_api_key.setter
    def openai_api_key(self, value: str):
        """Set OpenAI API key (offline mode only)."""
        self.offline_openai_key = value
    
    @property
    def gemini_api_key(self) -> str:
        """Get Gemini API key (offline mode only)."""
        if not self.offline_mode:
            return ""
        return self.offline_gemini_key
    
    @gemini_api_key.setter
    def gemini_api_key(self, value: str):
        self.offline_gemini_key = value
    
    @property
    def anthropic_api_key(self) -> str:
        """Get Anthropic API key (offline mode only)."""
        if not self.offline_mode:
            return ""
        return self.offline_anthropic_key
    
    @anthropic_api_key.setter
    def anthropic_api_key(self, value: str):
        self.offline_anthropic_key = value


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
