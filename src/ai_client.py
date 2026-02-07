"""AI client module for Chotto Voice."""
from abc import ABC, abstractmethod
from typing import Optional, Generator
import anthropic
import openai


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
    
    DEFAULT_SYSTEM_PROMPT = """あなたは音声入力テキストの整形ツールです。
入力されたテキストをそのまま整形して出力してください。

処理ルール：
1. フィラー（「あの」「あのー」「えー」「えーと」「まあ」「なんか」「こう」「その」等）を除去
2. 言い直しや重複を整理
3. 句読点を適切に追加
4. 明らかな言い間違いを修正

禁止事項：
- 内容に対する返答や回答をしない
- 質問に答えない
- 追加の説明や補足をしない
- 元の意図を変えない

入力テキストを整形した結果のみを出力してください。"""
    
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
    
    DEFAULT_SYSTEM_PROMPT = """あなたは音声入力テキストの整形ツールです。
入力されたテキストをそのまま整形して出力してください。

処理ルール：
1. フィラー（「あの」「あのー」「えー」「えーと」「まあ」「なんか」「こう」「その」等）を除去
2. 言い直しや重複を整理
3. 句読点を適切に追加
4. 明らかな言い間違いを修正

禁止事項：
- 内容に対する返答や回答をしない
- 質問に答えない
- 追加の説明や補足をしない
- 元の意図を変えない

入力テキストを整形した結果のみを出力してください。"""
    
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
    else:
        raise ValueError(f"Unknown AI provider: {provider}")
