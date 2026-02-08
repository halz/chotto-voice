"""AI client module for Chotto Voice."""
from abc import ABC, abstractmethod
from typing import Optional, Generator
import anthropic
import openai
from google import genai


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
    api_key: str,
    model: Optional[str] = None
) -> AIClient:
    """Factory function to create appropriate AI client."""
    if provider == "claude":
        return ClaudeClient(api_key, model or "claude-sonnet-4-20250514")
    elif provider == "openai":
        return OpenAIClient(api_key, model or "gpt-4o")
    elif provider == "gemini":
        return GeminiClient(api_key, model or "gemini-2.0-flash")
    else:
        raise ValueError(f"Unknown AI provider: {provider}")
