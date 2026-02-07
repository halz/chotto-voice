"""Hotkey management for Chotto Voice."""
import sys
import time
import threading
from typing import Callable, Optional
from dataclasses import dataclass
from enum import Enum
import keyboard


DEBUG = True  # Set to True for debugging

def debug_print(msg: str):
    """Print debug message and flush immediately."""
    if DEBUG:
        print(msg, file=sys.stderr, flush=True)


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
        
        key = self.config.key.lower().strip()
        
        debug_print(f"[Hotkey] Starting with key: '{key}'")
        debug_print(f"[Hotkey] SINGLE_MODIFIER_KEYS: {SINGLE_MODIFIER_KEYS}")
        debug_print(f"[Hotkey] Is single modifier: {key in SINGLE_MODIFIER_KEYS}")
        
        # Check if this is a single modifier key (needs special handling)
        if key in SINGLE_MODIFIER_KEYS:
            self._setup_single_modifier_hotkey(key)
        else:
            self._setup_combo_hotkey(key)
        
        self._registered = True
    
    def _setup_single_modifier_hotkey(self, key: str):
        """Setup hotkey for single modifier keys like right shift."""
        # For single modifier keys, we detect press and release
        # Double tap to start, single tap to stop
        self._modifier_press_time = 0
        self._modifier_tap_threshold = 0.5  # seconds for valid tap
        self._modifier_is_pressed = False
        self._last_tap_time = 0
        self._double_tap_threshold = 0.6  # seconds between taps for double-tap (wider window)
        
        # Normalize key for matching (handle ctrl/control variants)
        def normalize_key(k: str) -> str:
            """Normalize key name for comparison."""
            k = k.lower().strip().replace("_", " ")
            # Normalize ctrl <-> control
            k = k.replace("control", "ctrl")
            return k
        
        target_key = normalize_key(key)
        debug_print(f"[Hotkey] Setting up single modifier hotkey: '{target_key}'")
        
        def on_event(event):
            event_key = normalize_key(event.name)
            
            if event_key == target_key:
                if event.event_type == 'down':
                    if not self._modifier_is_pressed:
                        self._modifier_press_time = time.time()
                        self._modifier_is_pressed = True
                        debug_print(f"[Hotkey] Press detected: '{event_key}'")
                elif event.event_type == 'up':
                    if self._modifier_is_pressed:
                        self._modifier_is_pressed = False
                        elapsed = time.time() - self._modifier_press_time
                        debug_print(f"[Hotkey] Release detected: '{event_key}', elapsed: {elapsed:.3f}s")
                        
                        # Check if it was a valid tap
                        # Very low threshold for stopping (0.005s), higher for starting
                        min_threshold = 0.005 if self._is_recording else 0.02
                        if min_threshold < elapsed < self._modifier_tap_threshold:
                            current_time = time.time()
                            time_since_last_tap = current_time - self._last_tap_time
                            
                            if self._is_recording:
                                # If recording, single tap stops it
                                debug_print(f"[Hotkey] Single tap - stopping recording")
                                self._stop_recording()
                            elif time_since_last_tap < self._double_tap_threshold:
                                # Double tap detected - start recording
                                debug_print(f"[Hotkey] Double tap detected (gap: {time_since_last_tap:.3f}s) - starting recording")
                                self._start_recording()
                            else:
                                debug_print(f"[Hotkey] Single tap (gap: {time_since_last_tap:.3f}s > {self._double_tap_threshold}s, waiting)")
                            
                            self._last_tap_time = current_time
        
        keyboard.hook(on_event)
    
    def _setup_combo_hotkey(self, key: str):
        """Setup hotkey for key combinations."""
        try:
            keyboard.add_hotkey(
                key,
                self._on_hotkey_pressed,
                suppress=True,
                trigger_on_release=False
            )
        except Exception as e:
            print(f"Hotkey registration error: {e}")
            # Fallback
            keyboard.on_press_key(
                self._get_trigger_key(),
                self._on_key_down,
                suppress=False
            )
    
    def _on_hotkey_pressed(self):
        """Handle full hotkey combo press - toggle recording."""
        with self._lock:
            current_time = time.time()
            
            # Debounce - ignore if pressed too quickly
            if current_time - self._last_press_time < 0.2:
                return
            
            self._last_press_time = current_time
            
            # Toggle recording
            if self._is_recording:
                self._stop_recording()
            else:
                self._start_recording()
    
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
        """Handle key release - not used in toggle mode."""
        pass
    
    def _start_recording(self):
        """Start recording."""
        self._is_recording = True
        if self.on_record_start:
            self.on_record_start()
    
    def _stop_recording(self):
        """Stop recording."""
        self._is_recording = False
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
    
    def set_recording_state(self, is_recording: bool):
        """Set recording state (called from UI when recording starts/stops)."""
        self._is_recording = is_recording
    
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
    "右Alt (単体)": "right alt",
    "右Shift (単体)": "right shift",
    "右Ctrl (単体)": "right ctrl",
    "F9": "f9",
    "Ctrl+Alt+V": "ctrl+alt+v",
}

# Single modifier keys that need special handling
# Include both "ctrl" and "control" variants for compatibility
SINGLE_MODIFIER_KEYS = {
    "right alt", "left alt", 
    "right shift", "left shift", 
    "right ctrl", "left ctrl",
    "right control", "left control",
}
