"""AI client module for Chotto Voice."""
from abc import ABC, abstractmethod
from typing import Optional, Generator
import anthropic
import openai
import google.generativeai as genai


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
    
    DEFAULT_SYSTEM_PROMPT = """音声入力テキストを最小限の整形で出力してください。

処理すること：
- 文頭・文中のフィラーのみ除去（「えー」「えーと」「あのー」「うーん」「まあ」）
- 句読点を適切に追加

絶対にしないこと：
- 内容を要約・短縮しない
- 言い回しを変えない
- 単語を削除しない（フィラー以外）
- 文章構造を変えない
- 返答・回答・説明を追加しない

整形結果のみを出力。"""
    
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
    
    DEFAULT_SYSTEM_PROMPT = """音声入力テキストを最小限の整形で出力してください。

処理すること：
- 文頭・文中のフィラーのみ除去（「えー」「えーと」「あのー」「うーん」「まあ」）
- 句読点を適切に追加

絶対にしないこと：
- 内容を要約・短縮しない
- 言い回しを変えない
- 単語を削除しない（フィラー以外）
- 文章構造を変えない
- 返答・回答・説明を追加しない

整形結果のみを出力。"""
    
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
    
    DEFAULT_SYSTEM_PROMPT = """音声入力テキストを最小限の整形で出力してください。

処理すること：
- 文頭・文中のフィラーのみ除去（「えー」「えーと」「あのー」「うーん」「まあ」）
- 句読点を適切に追加

絶対にしないこと：
- 内容を要約・短縮しない
- 言い回しを変えない
- 単語を削除しない（フィラー以外）
- 文章構造を変えない
- 返答・回答・説明を追加しない

整形結果のみを出力。"""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=model,
            system_instruction=self.DEFAULT_SYSTEM_PROMPT
        )
    
    def process(self, text: str, system_prompt: Optional[str] = None) -> str:
        """Process text through Gemini."""
        if system_prompt:
            model = genai.GenerativeModel(
                model_name=self.model.model_name,
                system_instruction=system_prompt
            )
            response = model.generate_content(text)
        else:
            response = self.model.generate_content(text)
        return response.text
    
    def process_stream(
        self, 
        text: str, 
        system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Process text through Gemini with streaming."""
        if system_prompt:
            model = genai.GenerativeModel(
                model_name=self.model.model_name,
                system_instruction=system_prompt
            )
            response = model.generate_content(text, stream=True)
        else:
            response = self.model.generate_content(text, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text


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
