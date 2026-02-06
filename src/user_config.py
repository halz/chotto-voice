"""User configuration management for Chotto Voice.

Persists user settings (hotkey, startup options) to a JSON file.
Settings are stored in the user's config directory.
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
    
    # Hotkey settings
    hotkey: str = "ctrl+shift+space"
    hotkey_double_tap_threshold: float = 0.3
    hotkey_hold_threshold: float = 0.2
    
    # UI settings
    auto_type: bool = True
    process_with_ai: bool = True
    
    # Startup settings
    start_with_windows: bool = False
    start_minimized: bool = True
    
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
