"""Hotkey management for Chotto Voice."""
import time
import threading
from typing import Callable, Optional
from dataclasses import dataclass
from enum import Enum
import keyboard


class HotkeyAction(Enum):
    """Hotkey action types."""
    HOLD_RECORD = "hold_record"           # Hold to record
    DOUBLE_TAP_MUTE = "double_tap_mute"   # Double-tap to record + mute


@dataclass
class HotkeyConfig:
    """Hotkey configuration."""
    key: str = "ctrl+shift+space"  # Default hotkey
    double_tap_threshold: float = 0.3  # Seconds between taps for double-tap
    hold_threshold: float = 0.2  # Seconds to consider as "hold"


class HotkeyManager:
    """Manages global hotkeys for voice recording."""
    
    def __init__(
        self,
        config: Optional[HotkeyConfig] = None,
        on_record_start: Optional[Callable[[], None]] = None,
        on_record_stop: Optional[Callable[[], None]] = None,
        on_mute_toggle: Optional[Callable[[bool], None]] = None
    ):
        self.config = config or HotkeyConfig()
        self.on_record_start = on_record_start
        self.on_record_stop = on_record_stop
        self.on_mute_toggle = on_mute_toggle
        
        self._is_recording = False
        self._is_muted = False
        self._last_press_time: float = 0
        self._press_count: int = 0
        self._key_held = False
        self._hold_timer: Optional[threading.Timer] = None
        self._registered = False
        self._lock = threading.Lock()
    
    def start(self):
        """Start listening for hotkeys."""
        if self._registered:
            return
        
        # Use add_hotkey for proper suppression of the full key combo
        try:
            keyboard.add_hotkey(
                self.config.key,
                self._on_hotkey_pressed,
                suppress=True,
                trigger_on_release=False
            )
            
            # Also listen for release of the main key
            keyboard.on_release_key(
                self._get_trigger_key(),
                self._on_key_up,
                suppress=False
            )
        except Exception as e:
            print(f"Hotkey registration error: {e}")
            # Fallback to old method
            keyboard.on_press_key(
                self._get_trigger_key(),
                self._on_key_down,
                suppress=False
            )
            keyboard.on_release_key(
                self._get_trigger_key(),
                self._on_key_up,
                suppress=False
            )
        
        self._registered = True
    
    def _on_hotkey_pressed(self):
        """Handle full hotkey combo press."""
        with self._lock:
            current_time = time.time()
            
            # Check for double-tap
            if current_time - self._last_press_time < self.config.double_tap_threshold:
                self._press_count += 1
            else:
                self._press_count = 1
            
            self._last_press_time = current_time
            
            # Double-tap detected
            if self._press_count >= 2:
                self._press_count = 0
                self._handle_double_tap()
                return
            
            # Start hold timer
            self._key_held = True
            if self._hold_timer:
                self._hold_timer.cancel()
            
            self._hold_timer = threading.Timer(
                self.config.hold_threshold,
                self._handle_hold_start
            )
            self._hold_timer.start()
    
    def stop(self):
        """Stop listening for hotkeys."""
        if not self._registered:
            return
        
        try:
            keyboard.remove_hotkey(self.config.key)
        except:
            pass
        keyboard.unhook_all()
        self._registered = False
    
    def _get_trigger_key(self) -> str:
        """Get the trigger key from hotkey combo."""
        # For combo like "ctrl+shift+space", we track "space" 
        # and check modifiers separately
        parts = self.config.key.lower().split("+")
        return parts[-1]  # Last part is the main key
    
    def _check_modifiers(self) -> bool:
        """Check if required modifier keys are pressed."""
        parts = self.config.key.lower().split("+")
        modifiers = parts[:-1]  # All except last
        
        for mod in modifiers:
            if mod in ("ctrl", "control"):
                if not keyboard.is_pressed("ctrl"):
                    return False
            elif mod == "shift":
                if not keyboard.is_pressed("shift"):
                    return False
            elif mod == "alt":
                if not keyboard.is_pressed("alt"):
                    return False
            elif mod in ("win", "windows", "super"):
                if not keyboard.is_pressed("win"):
                    return False
        
        return True
    
    def _on_key_down(self, event):
        """Handle key press (fallback method)."""
        if not self._check_modifiers():
            return
        
        # Delegate to hotkey handler
        self._on_hotkey_pressed()
    
    def _on_key_up(self, event):
        """Handle key release."""
        with self._lock:
            self._key_held = False
            
            # Cancel hold timer if released too quickly
            if self._hold_timer:
                self._hold_timer.cancel()
                self._hold_timer = None
            
            # Stop recording if it was started by hold
            if self._is_recording:
                self._stop_recording()
    
    def _handle_hold_start(self):
        """Handle hold gesture - start recording."""
        with self._lock:
            if self._key_held and not self._is_recording:
                # Block all keyboard input while recording
                self._block_keyboard()
                self._start_recording()
    
    def _handle_double_tap(self):
        """Handle double-tap gesture - toggle mute and start recording."""
        # Toggle mute
        self._is_muted = not self._is_muted
        if self.on_mute_toggle:
            self.on_mute_toggle(self._is_muted)
        
        # Start recording (will stop on key release)
        if not self._is_recording:
            self._start_recording()
    
    def _block_keyboard(self):
        """Block keyboard input during recording."""
        try:
            # Block common keys that might interfere
            # Note: This is a simple approach, may need refinement
            self._keyboard_blocked = True
        except Exception:
            pass
    
    def _unblock_keyboard(self):
        """Unblock keyboard input."""
        try:
            self._keyboard_blocked = False
        except Exception:
            pass
    
    def _start_recording(self):
        """Start recording."""
        self._is_recording = True
        if self.on_record_start:
            self.on_record_start()
    
    def _stop_recording(self):
        """Stop recording."""
        self._is_recording = False
        self._unblock_keyboard()
        if self.on_record_stop:
            self.on_record_stop()
    
    def update_hotkey(self, new_key: str):
        """Update the hotkey."""
        was_registered = self._registered
        if was_registered:
            self.stop()
        
        self.config.key = new_key
        
        if was_registered:
            self.start()
    
    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording
    
    @property
    def is_muted(self) -> bool:
        """Check if speakers are muted."""
        return self._is_muted


# Common hotkey presets
HOTKEY_PRESETS = {
    "Ctrl+Shift+Space": "ctrl+shift+space",
    "Ctrl+Alt+V": "ctrl+alt+v",
    "F9": "f9",
    "Ctrl+`": "ctrl+`",
    "Win+H": "win+h",
}
