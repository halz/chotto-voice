"""Speech-to-text transcription module for Chotto Voice."""
from abc import ABC, abstractmethod
from typing import Optional


class Transcriber(ABC):
    """Abstract base class for speech-to-text transcription."""
    
    @abstractmethod
    def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio data to text."""
        pass


class OpenAIWhisperTranscriber(Transcriber):
    """Transcriber using OpenAI Whisper API."""
    
    def __init__(self, api_key: str, model: str = "whisper-1"):
        import openai
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
    
    def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio using OpenAI Whisper API."""
        if not audio_data:
            return ""
        
        # Create a file-like object from bytes
        import io
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.wav"
        
        response = self.client.audio.transcriptions.create(
            model=self.model,
            file=audio_file,
            language="ja"  # Japanese
        )
        
        return response.text


class LocalWhisperTranscriber(Transcriber):
    """Transcriber using local Whisper model."""
    
    def __init__(self, model_name: str = "base"):
        self.model_name = model_name
        self._model = None
    
    def _get_model_dir(self) -> Optional[str]:
        """Get bundled whisper model directory if available."""
        import sys
        import os
        
        # Check for bundled models (portable build)
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            bundled = os.path.join(exe_dir, "models", "whisper")
            if os.path.exists(bundled):
                return bundled
        else:
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            local = os.path.join(script_dir, "models", "whisper")
            if os.path.exists(local):
                return local
        
        return None
    
    def _load_model(self):
        """Lazy load the Whisper model."""
        if self._model is None:
            import whisper
            model_dir = self._get_model_dir()
            if model_dir:
                print(f"[Whisper] Loading from bundled: {model_dir}", flush=True)
                self._model = whisper.load_model(self.model_name, download_root=model_dir)
            else:
                self._model = whisper.load_model(self.model_name)
    
    def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio using local Whisper model."""
        if not audio_data:
            return ""
        
        self._load_model()
        
        # Save to temp file (whisper requires file path)
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name
        
        try:
            result = self._model.transcribe(temp_path, language="ja")
            return result["text"]
        finally:
            os.unlink(temp_path)


def create_transcriber(
    provider: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> Transcriber:
    """Factory function to create appropriate transcriber."""
    if provider == "openai_api":
        if not api_key:
            raise ValueError("OpenAI API key required for Whisper API")
        return OpenAIWhisperTranscriber(api_key, model or "whisper-1")
    elif provider == "local":
        return LocalWhisperTranscriber(model or "base")
    else:
        raise ValueError(f"Unknown transcriber provider: {provider}")
