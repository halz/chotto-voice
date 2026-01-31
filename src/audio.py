"""Audio capture module for Chotto Voice."""
import io
import wave
import threading
from typing import Callable, Optional
import numpy as np
import sounddevice as sd


class AudioRecorder:
    """Records audio from the microphone."""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        on_audio_level: Optional[Callable[[float], None]] = None
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_audio_level = on_audio_level
        
        self._recording = False
        self._frames: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()
    
    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Callback for audio stream."""
        if status:
            print(f"Audio status: {status}")
        
        with self._lock:
            if self._recording:
                self._frames.append(indata.copy())
                
                # Calculate audio level for visualization
                if self.on_audio_level:
                    level = np.abs(indata).mean()
                    self.on_audio_level(float(level))
    
    def start_recording(self):
        """Start recording audio."""
        with self._lock:
            self._frames = []
            self._recording = True
        
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=np.float32,
            callback=self._audio_callback
        )
        self._stream.start()
    
    def stop_recording(self) -> bytes:
        """Stop recording and return audio as WAV bytes."""
        with self._lock:
            self._recording = False
        
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        
        # Convert frames to WAV
        with self._lock:
            if not self._frames:
                return b""
            
            audio_data = np.concatenate(self._frames, axis=0)
        
        # Convert float32 to int16 for WAV
        audio_int16 = (audio_data * 32767).astype(np.int16)
        
        # Create WAV in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_int16.tobytes())
        
        return wav_buffer.getvalue()
    
    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording
    
    @staticmethod
    def list_devices() -> list[dict]:
        """List available audio input devices."""
        devices = sd.query_devices()
        input_devices = []
        for i, device in enumerate(devices):
            if device["max_input_channels"] > 0:
                input_devices.append({
                    "index": i,
                    "name": device["name"],
                    "channels": device["max_input_channels"],
                    "sample_rate": device["default_samplerate"]
                })
        return input_devices
