"""System audio control for Chotto Voice."""
import sys
import time
import threading
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
    
    @abstractmethod
    def fade_out(self, duration: float = 0.3) -> bool:
        """Fade out system audio over duration seconds."""
        pass
    
    @abstractmethod
    def fade_in(self, duration: float = 0.3) -> bool:
        """Fade in system audio over duration seconds."""
        pass
    
    @abstractmethod
    def get_volume(self) -> float:
        """Get current volume level (0.0 to 1.0)."""
        pass
    
    @abstractmethod
    def set_volume(self, level: float) -> bool:
        """Set volume level (0.0 to 1.0)."""
        pass


class WindowsAudioController(AudioController):
    """Audio controller for Windows using pycaw - per-app volume control."""
    
    def __init__(self):
        self._interface = None
        self._saved_volumes = {}  # {pid: volume} for each app
        self._fade_thread = None
        self._use_per_app = True  # Use per-app volume (no OSD)
        self._init_audio()
    
    def _init_audio(self):
        """Initialize Windows audio interface."""
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            
            # Get default audio endpoint for fallback
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            self._interface = cast(interface, POINTER(IAudioEndpointVolume))
        except ImportError:
            # pycaw not installed - silently disable
            self._interface = None
        except Exception:
            # Audio control not available - silently disable
            # This is not critical, the app works without it
            self._interface = None
    
    def _get_audio_sessions(self):
        """Get all active audio sessions (playing apps)."""
        try:
            from pycaw.pycaw import AudioUtilities
            sessions = AudioUtilities.GetAllSessions()
            return [s for s in sessions if s.Process and s.Process.pid]
        except Exception:
            return []
    
    def get_volume(self) -> float:
        """Get current system volume level (0.0 to 1.0)."""
        if not self._interface:
            return 1.0
        try:
            return self._interface.GetMasterVolumeLevelScalar()
        except Exception:
            return 1.0
    
    def set_volume(self, level: float) -> bool:
        """Set system volume level (0.0 to 1.0)."""
        if not self._interface:
            return False
        try:
            level = max(0.0, min(1.0, level))
            self._interface.SetMasterVolumeLevelScalar(level, None)
            return True
        except Exception:
            return False
    
    def _set_all_app_volumes(self, level: float) -> bool:
        """Set volume for all audio-playing apps (no OSD)."""
        try:
            sessions = self._get_audio_sessions()
            for session in sessions:
                try:
                    volume = session._ctl.QueryInterface(
                        __import__('pycaw.pycaw', fromlist=['ISimpleAudioVolume']).ISimpleAudioVolume
                    )
                    volume.SetMasterVolume(level, None)
                except Exception:
                    pass
            return True
        except Exception as e:
            print(f"Per-app volume error: {e}")
            return False
    
    def _save_app_volumes(self):
        """Save current volume of all audio apps."""
        self._saved_volumes = {}
        try:
            from pycaw.pycaw import ISimpleAudioVolume
            sessions = self._get_audio_sessions()
            for session in sessions:
                try:
                    volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                    self._saved_volumes[session.Process.pid] = volume.GetMasterVolume()
                except Exception:
                    pass
        except Exception:
            pass
    
    def _restore_app_volumes(self):
        """Restore saved volumes for all audio apps."""
        try:
            from pycaw.pycaw import ISimpleAudioVolume
            sessions = self._get_audio_sessions()
            for session in sessions:
                try:
                    pid = session.Process.pid
                    if pid in self._saved_volumes:
                        volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                        volume.SetMasterVolume(self._saved_volumes[pid], None)
                except Exception:
                    pass
        except Exception:
            pass
    
    def fade_out(self, duration: float = 0.3) -> bool:
        """Fade out audio over duration seconds (per-app, no OSD)."""
        try:
            self._save_app_volumes()
            
            if not self._saved_volumes:
                return True  # No apps playing audio
            
            steps = 10
            step_duration = duration / steps
            
            def do_fade():
                for i in range(steps):
                    factor = 1.0 - ((i + 1) / steps)
                    try:
                        from pycaw.pycaw import ISimpleAudioVolume
                        sessions = self._get_audio_sessions()
                        for session in sessions:
                            try:
                                pid = session.Process.pid
                                if pid in self._saved_volumes:
                                    volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                                    volume.SetMasterVolume(self._saved_volumes[pid] * factor, None)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    time.sleep(step_duration)
                
                # Set to 0 at the end
                self._set_all_app_volumes(0.0)
            
            self._fade_thread = threading.Thread(target=do_fade, daemon=True)
            self._fade_thread.start()
            return True
        except Exception as e:
            print(f"Fade out error: {e}")
            return self.mute()
    
    def fade_in(self, duration: float = 0.3) -> bool:
        """Fade in audio over duration seconds (per-app, no OSD)."""
        try:
            if not self._saved_volumes:
                return True  # Nothing to restore
            
            steps = 10
            step_duration = duration / steps
            
            def do_fade():
                for i in range(steps):
                    factor = (i + 1) / steps
                    try:
                        from pycaw.pycaw import ISimpleAudioVolume
                        sessions = self._get_audio_sessions()
                        for session in sessions:
                            try:
                                pid = session.Process.pid
                                if pid in self._saved_volumes:
                                    volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                                    volume.SetMasterVolume(self._saved_volumes[pid] * factor, None)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    time.sleep(step_duration)
                
                # Restore original volumes
                self._restore_app_volumes()
            
            self._fade_thread = threading.Thread(target=do_fade, daemon=True)
            self._fade_thread.start()
            return True
        except Exception as e:
            print(f"Fade in error: {e}")
            return self.unmute()
    
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


class MacAudioController(AudioController):
    """Audio controller for macOS using osascript/AppleScript."""
    
    def __init__(self):
        import subprocess
        self._subprocess = subprocess
        self._saved_volume: float = 1.0
        self._fade_thread = None
    
    def _run_osascript(self, script: str) -> str:
        """Run AppleScript and return output."""
        try:
            result = self._subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                check=False
            )
            return result.stdout.strip()
        except Exception:
            return ""
    
    def get_volume(self) -> float:
        """Get current volume level (0.0 to 1.0)."""
        try:
            output = self._run_osascript("output volume of (get volume settings)")
            return int(output) / 100.0
        except Exception:
            return 1.0
    
    def set_volume(self, level: float) -> bool:
        """Set volume level (0.0 to 1.0)."""
        try:
            level = max(0.0, min(1.0, level))
            volume_int = int(level * 100)
            self._run_osascript(f"set volume output volume {volume_int}")
            return True
        except Exception:
            return False
    
    def is_muted(self) -> bool:
        """Check if system audio is muted."""
        try:
            output = self._run_osascript("output muted of (get volume settings)")
            return output.lower() == "true"
        except Exception:
            return False
    
    def mute(self) -> bool:
        """Mute system audio."""
        try:
            self._run_osascript("set volume output muted true")
            return True
        except Exception:
            return False
    
    def unmute(self) -> bool:
        """Unmute system audio."""
        try:
            self._run_osascript("set volume output muted false")
            return True
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
    
    def fade_out(self, duration: float = 0.3) -> bool:
        """Fade out system audio over duration seconds."""
        try:
            self._saved_volume = self.get_volume()
            if self._saved_volume <= 0:
                return True
            
            steps = 10
            step_duration = duration / steps
            
            def do_fade():
                current = self._saved_volume
                for i in range(steps):
                    current = self._saved_volume * (1.0 - ((i + 1) / steps))
                    self.set_volume(current)
                    time.sleep(step_duration)
                self.set_volume(0.0)
            
            self._fade_thread = threading.Thread(target=do_fade, daemon=True)
            self._fade_thread.start()
            return True
        except Exception:
            return self.mute()
    
    def fade_in(self, duration: float = 0.3) -> bool:
        """Fade in system audio over duration seconds."""
        try:
            if self._saved_volume <= 0:
                self._saved_volume = 0.5  # Default to 50% if nothing saved
            
            steps = 10
            step_duration = duration / steps
            
            def do_fade():
                for i in range(steps):
                    current = self._saved_volume * ((i + 1) / steps)
                    self.set_volume(current)
                    time.sleep(step_duration)
                self.set_volume(self._saved_volume)
            
            self._fade_thread = threading.Thread(target=do_fade, daemon=True)
            self._fade_thread.start()
            return True
        except Exception:
            return self.unmute()


class DummyAudioController(AudioController):
    """Dummy audio controller for unsupported systems."""
    
    def __init__(self):
        self._muted = False
        self._volume = 1.0
    
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
    
    def get_volume(self) -> float:
        return self._volume
    
    def set_volume(self, level: float) -> bool:
        self._volume = max(0.0, min(1.0, level))
        return True
    
    def fade_out(self, duration: float = 0.3) -> bool:
        self._volume = 0.0
        return True
    
    def fade_in(self, duration: float = 0.3) -> bool:
        self._volume = 1.0
        return True


def get_audio_controller() -> AudioController:
    """Get the appropriate audio controller for the current platform."""
    if sys.platform == "win32":
        try:
            return WindowsAudioController()
        except ImportError:
            print("pycaw not installed, using dummy audio controller")
            return DummyAudioController()
    elif sys.platform == "darwin":
        # macOS - use AppleScript via osascript
        return MacAudioController()
    else:
        # Linux - could add PulseAudio/PipeWire support later
        return DummyAudioController()
