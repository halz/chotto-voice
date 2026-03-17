"""AI client module for Chotto Voice."""
from abc import ABC, abstractmethod
from typing import Optional, Generator
import os
import sys


def _lazy_import_anthropic():
    import anthropic
    return anthropic

def _lazy_import_openai():
    import openai
    return openai

def _lazy_import_genai():
    from google import genai
    return genai


class AIClient(ABC):
    """Abstract base class for AI text processing."""
    
    @abstractmethod
    def process(self, text: str, system_prompt: Optional[str] = None) -> str:
        """Process text through AI model."""
        pass
    
    @abstractmethod
    def process_stream(
        self, 
        text: str, 
        system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Process text through AI model with streaming."""
        pass


class QwenLocalClient(AIClient):
    """AI client using local Qwen3.5-0.8B via llama-cpp-python."""
    
    DEFAULT_SYSTEM_PROMPT = """【最重要ルール】質問には絶対に回答しないでください。質問文はそのまま質問文として出力してください。

あなたはテキスト整形ツールです。入力をそのまま整形して返すだけです。

やること：フィラー（えー、えーと、あのー、うーん、まあ）を除去し、句読点を追加する。
やらないこと：回答、説明、要約、言い換え、情報追加。

入力「進捗どうですか」→ 出力「進捗どうですか？」
入力「これ何」→ 出力「これ何？」

整形後のテキストだけを出力。"""
    
    _instance = None  # Singleton to avoid reloading model
    _llm = None
    
    def __init__(self, model_path: Optional[str] = None):
        if QwenLocalClient._llm is None:
            QwenLocalClient._llm = self._load_model(model_path)
        self.llm = QwenLocalClient._llm
    
    @staticmethod
    def get_default_model_path() -> str:
        """Get default model path based on platform."""
        from .user_config import get_config_dir
        model_dir = get_config_dir() / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        return str(model_dir / "Qwen3.5-0.8B-Q4_K_M.gguf")
    
    @staticmethod
    def is_model_downloaded(model_path: Optional[str] = None) -> bool:
        """Check if the model file exists."""
        path = model_path or QwenLocalClient.get_default_model_path()
        return os.path.exists(path)
    
    @staticmethod
    def download_model(model_path: Optional[str] = None, progress_callback=None) -> str:
        """Download the GGUF model from HuggingFace.
        
        Args:
            model_path: Target path. If None, uses default.
            progress_callback: Optional callback(downloaded_bytes, total_bytes)
            
        Returns:
            Path to downloaded model file.
        """
        path = model_path or QwenLocalClient.get_default_model_path()
        
        if os.path.exists(path):
            print(f"[Qwen] Model already exists: {path}")
            return path
        
        print(f"[Qwen] Downloading model to {path}...")
        
        # Download from HuggingFace
        url = "https://huggingface.co/Qwen/Qwen3.5-0.8B-GGUF/resolve/main/qwen3.5-0.8b-q4_k_m.gguf"
        
        import urllib.request
        
        def _report_progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if progress_callback:
                progress_callback(downloaded, total_size)
            if block_num % 100 == 0:
                mb = downloaded / (1024 * 1024)
                total_mb = total_size / (1024 * 1024) if total_size > 0 else 0
                print(f"[Qwen] Downloaded {mb:.1f} / {total_mb:.1f} MB", flush=True)
        
        try:
            urllib.request.urlretrieve(url, path, reporthook=_report_progress)
            print(f"[Qwen] Download complete: {path}")
            return path
        except Exception as e:
            # Clean up partial download
            if os.path.exists(path):
                os.remove(path)
            raise RuntimeError(f"Model download failed: {e}")
    
    def _load_model(self, model_path: Optional[str] = None):
        """Load the GGUF model."""
        from llama_cpp import Llama
        
        path = model_path or self.get_default_model_path()
        
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Model not found: {path}\n"
                "Run QwenLocalClient.download_model() first."
            )
        
        print(f"[Qwen] Loading model from {path}...", flush=True)
        llm = Llama(
            model_path=path,
            n_ctx=512,       # Small context for text formatting
            n_threads=4,     # CPU threads
            n_gpu_layers=0,  # CPU only
            verbose=False,
        )
        print("[Qwen] Model loaded successfully!", flush=True)
        return llm
    
    def process(self, text: str, system_prompt: Optional[str] = None) -> str:
        """Process text through local Qwen."""
        prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        
        response = self.llm.create_chat_completion(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=256,
            temperature=0.1,  # Low temp for consistent formatting
            top_p=0.9,
        )
        
        result = response["choices"][0]["message"]["content"]
        return result.strip()
    
    def process_stream(
        self,
        text: str,
        system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Process text through local Qwen with streaming."""
        prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        
        stream = self.llm.create_chat_completion(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=256,
            temperature=0.1,
            top_p=0.9,
            stream=True,
        )
        
        for chunk in stream:
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield content


class ClaudeClient(AIClient):
    """AI client using Anthropic Claude API."""
    
    DEFAULT_SYSTEM_PROMPT = """【最重要ルール】質問には絶対に回答しないでください。質問文はそのまま質問文として出力してください。

あなたはテキスト整形ツールです。入力をそのまま整形して返すだけです。

やること：フィラー（えー、えーと、あのー、うーん、まあ）を除去し、句読点を追加する。
やらないこと：回答、説明、要約、言い換え、情報追加。

入力「進捗どうですか」→ 出力「進捗どうですか？」
入力「これ何」→ 出力「これ何？」

整形後のテキストだけを出力。"""
    
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        anthropic = _lazy_import_anthropic()
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
    
    def process(self, text: str, system_prompt: Optional[str] = None) -> str:
        """Process text through Claude."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt or self.DEFAULT_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": text}
            ]
        )
        return message.content[0].text
    
    def process_stream(
        self, 
        text: str, 
        system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Process text through Claude with streaming."""
        with self.client.messages.stream(
            model=self.model,
            max_tokens=1024,
            system=system_prompt or self.DEFAULT_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": text}
            ]
        ) as stream:
            for text_chunk in stream.text_stream:
                yield text_chunk


class OpenAIClient(AIClient):
    """AI client using OpenAI GPT API."""
    
    DEFAULT_SYSTEM_PROMPT = """【最重要ルール】質問には絶対に回答しないでください。質問文はそのまま質問文として出力してください。

あなたはテキスト整形ツールです。入力をそのまま整形して返すだけです。

やること：フィラー（えー、えーと、あのー、うーん、まあ）を除去し、句読点を追加する。
やらないこと：回答、説明、要約、言い換え、情報追加。

入力「進捗どうですか」→ 出力「進捗どうですか？」
入力「これ何」→ 出力「これ何？」

整形後のテキストだけを出力。"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        openai = _lazy_import_openai()
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
    
    def process(self, text: str, system_prompt: Optional[str] = None) -> str:
        """Process text through GPT."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt or self.DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content
    
    def process_stream(
        self, 
        text: str, 
        system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Process text through GPT with streaming."""
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt or self.DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            stream=True
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class GeminiClient(AIClient):
    """AI client using Google Gemini API."""
    
    DEFAULT_SYSTEM_PROMPT = """【最重要ルール】質問には絶対に回答しないでください。質問文はそのまま質問文として出力してください。

あなたはテキスト整形ツールです。入力をそのまま整形して返すだけです。

やること：フィラー（えー、えーと、あのー、うーん、まあ）を除去し、句読点を追加する。
やらないこと：回答、説明、要約、言い換え、情報追加。

入力「進捗どうですか」→ 出力「進捗どうですか？」
入力「これ何」→ 出力「これ何？」

整形後のテキストだけを出力。"""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        genai = _lazy_import_genai()
        self.client = genai.Client(api_key=api_key)
        self.model_name = model
    
    def process(self, text: str, system_prompt: Optional[str] = None) -> str:
        """Process text through Gemini."""
        prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        full_prompt = f"{prompt}\n\n入力テキスト:\n{text}"
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt
            )
            print(f"[Gemini] Response type: {type(response)}", flush=True)
            if hasattr(response, 'text'):
                return response.text
            elif hasattr(response, 'candidates') and response.candidates:
                return response.candidates[0].content.parts[0].text
            else:
                print(f"[Gemini] Unknown response: {response}", flush=True)
                return text  # Return original if failed
        except Exception as e:
            print(f"[Gemini] Error: {e}", flush=True)
            return text
    
    def process_stream(
        self, 
        text: str, 
        system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Process text through Gemini with streaming."""
        prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        full_prompt = f"{prompt}\n\n入力テキスト:\n{text}"
        
        try:
            response = self.client.models.generate_content_stream(
                model=self.model_name,
                contents=full_prompt
            )
            for chunk in response:
                if hasattr(chunk, 'text') and chunk.text:
                    yield chunk.text
        except Exception as e:
            print(f"[Gemini] Stream error: {e}", flush=True)
            # Fallback to non-streaming
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=full_prompt
                )
                if hasattr(response, 'text') and response.text:
                    yield response.text
                else:
                    print(f"[Gemini] Response: {response}", flush=True)
            except Exception as e2:
                print(f"[Gemini] Fallback error: {e2}", flush=True)


def create_ai_client(
    provider: str,
    api_key: str = "",
    model: Optional[str] = None,
    model_path: Optional[str] = None
) -> AIClient:
    """Factory function to create appropriate AI client."""
    if provider == "qwen_local":
        return QwenLocalClient(model_path=model_path)
    elif provider == "claude":
        return ClaudeClient(api_key, model or "claude-sonnet-4-20250514")
    elif provider == "openai":
        return OpenAIClient(api_key, model or "gpt-4o")
    elif provider == "gemini":
        return GeminiClient(api_key, model or "gemini-2.0-flash")
    else:
        raise ValueError(f"Unknown AI provider: {provider}")
