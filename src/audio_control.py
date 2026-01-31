"""System audio control for Chotto Voice."""
import sys
from abc import ABC, abstractmethod


class AudioController(ABC):
    """Abstract base class for system audio control."""
    
    @abstractmethod
    def mute(self) -> bool:
        """Mute system audio. Returns success status."""
        pass
    
    @abstractmethod
    def unmute(self) -> bool:
        """Unmute system audio. Returns success status."""
        pass
    
    @abstractmethod
    def is_muted(self) -> bool:
        """Check if system audio is muted."""
        pass
    
    @abstractmethod
    def toggle_mute(self) -> bool:
        """Toggle mute state. Returns new mute state."""
        pass


class WindowsAudioController(AudioController):
    """Audio controller for Windows using pycaw."""
    
    def __init__(self):
        self._interface = None
        self._init_audio()
    
    def _init_audio(self):
        """Initialize Windows audio interface."""
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            
            # Get default audio endpoint
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            self._interface = cast(interface, POINTER(IAudioEndpointVolume))
        except ImportError:
            print("pycaw not installed, audio control disabled")
            self._interface = None
        except AttributeError:
            # Try alternative method for newer pycaw versions
            try:
                from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
                # Fall back to dummy controller
                print("Using fallback audio controller")
                self._interface = None
            except:
                self._interface = None
        except Exception as e:
            print(f"Failed to initialize Windows audio: {e}")
            self._interface = None
    
    def mute(self) -> bool:
        """Mute system audio."""
        if not self._interface:
            return self._mute_fallback()
        try:
            self._interface.SetMute(1, None)
            return True
        except Exception:
            return self._mute_fallback()
    
    def unmute(self) -> bool:
        """Unmute system audio."""
        if not self._interface:
            return self._unmute_fallback()
        try:
            self._interface.SetMute(0, None)
            return True
        except Exception:
            return self._unmute_fallback()
    
    def is_muted(self) -> bool:
        """Check if system audio is muted."""
        if not self._interface:
            return False
        try:
            return bool(self._interface.GetMute())
        except Exception:
            return False
    
    def toggle_mute(self) -> bool:
        """Toggle mute state. Returns new mute state."""
        if self.is_muted():
            self.unmute()
            return False
        else:
            self.mute()
            return True
    
    def _mute_fallback(self) -> bool:
        """Fallback mute using nircmd or keyboard simulation."""
        try:
            import subprocess
            # Try using nircmd if available
            subprocess.run(['nircmd', 'mutesysvolume', '1'], 
                          capture_output=True, check=False)
            return True
        except:
            pass
        
        try:
            # Try keyboard simulation
            import keyboard
            keyboard.press_and_release('volume mute')
            return True
        except:
            return False
    
    def _unmute_fallback(self) -> bool:
        """Fallback unmute."""
        try:
            import subprocess
            subprocess.run(['nircmd', 'mutesysvolume', '0'], 
                          capture_output=True, check=False)
            return True
        except:
            pass
        
        try:
            import keyboard
            keyboard.press_and_release('volume mute')
            return True
        except:
            return False


class DummyAudioController(AudioController):
    """Dummy audio controller for non-Windows systems."""
    
    def __init__(self):
        self._muted = False
    
    def mute(self) -> bool:
        self._muted = True
        return True
    
    def unmute(self) -> bool:
        self._muted = False
        return True
    
    def is_muted(self) -> bool:
        return self._muted
    
    def toggle_mute(self) -> bool:
        self._muted = not self._muted
        return self._muted


def get_audio_controller() -> AudioController:
    """Get the appropriate audio controller for the current platform."""
    if sys.platform == "win32":
        try:
            return WindowsAudioController()
        except ImportError:
            print("pycaw not installed, using dummy audio controller")
            return DummyAudioController()
    else:
        # macOS/Linux - could add support later
        return DummyAudioController()
