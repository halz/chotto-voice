"""AI client module for Chotto Voice.

Provides a unified interface over industry-standard AI providers plus any
OpenAI-compatible endpoint (Ollama, LM Studio, or a custom server). Each
provider is described once in ``PROVIDERS`` so the UI can render the available
choices generically.

All provider SDKs are imported lazily inside the client constructors so a
missing optional dependency (e.g. ``google-genai``) never prevents the app from
starting.
"""
from abc import ABC, abstractmethod
from typing import Optional, Generator
from dataclasses import dataclass, field


# Single source of truth for the formatting prompt (previously duplicated
# across every client class).
DEFAULT_SYSTEM_PROMPT = """【最重要ルール】質問には絶対に回答しないでください。質問文はそのまま質問文として出力してください。

あなたはテキスト整形ツールです。入力をそのまま整形して返すだけです。

やること：フィラー（えー、えーと、あのー、うーん、まあ）を除去し、句読点を追加し、明らかな誤変換を直す。
やらないこと：回答、説明、要約、言い換え、情報追加。

入力「進捗どうですか」→ 出力「進捗どうですか？」
入力「これ何」→ 出力「これ何？」

整形後のテキストだけを出力。"""


@dataclass(frozen=True)
class ProviderSpec:
    """Describes a selectable AI provider for the settings UI."""

    key: str                       # stable identifier stored in config
    label: str                     # human-readable name shown in the UI
    kind: str                      # "anthropic" | "gemini" | "openai_compatible"
    needs_api_key: bool            # whether an API key is required
    api_key_optional: bool = False  # key accepted but not required (local servers)
    needs_base_url: bool = False   # whether a base URL is configurable
    default_base_url: str = ""     # pre-filled base URL for local servers
    default_model: str = ""        # pre-filled model name
    api_key_url: str = ""          # where the user can obtain a key


# Industry-standard providers first, then OpenAI-compatible local/custom servers.
PROVIDERS: dict[str, ProviderSpec] = {
    "gemini": ProviderSpec(
        key="gemini",
        label="Google Gemini（無料）",
        kind="gemini",
        needs_api_key=True,
        default_model="gemini-2.0-flash",
        api_key_url="https://aistudio.google.com/app/apikey",
    ),
    "claude": ProviderSpec(
        key="claude",
        label="Anthropic Claude",
        kind="anthropic",
        needs_api_key=True,
        # Latency-critical formatting micro-task → fast model by default.
        # Fully overridable from the settings UI.
        default_model="claude-haiku-4-5",
        api_key_url="https://console.anthropic.com/settings/keys",
    ),
    "openai": ProviderSpec(
        key="openai",
        label="OpenAI",
        kind="openai_compatible",
        needs_api_key=True,
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        api_key_url="https://platform.openai.com/api-keys",
    ),
    "ollama": ProviderSpec(
        key="ollama",
        label="Ollama（ローカル）",
        kind="openai_compatible",
        needs_api_key=False,
        api_key_optional=True,
        needs_base_url=True,
        default_base_url="http://localhost:11434/v1",
        default_model="llama3.1",
    ),
    "lmstudio": ProviderSpec(
        key="lmstudio",
        label="LM Studio（ローカル）",
        kind="openai_compatible",
        needs_api_key=False,
        api_key_optional=True,
        needs_base_url=True,
        default_base_url="http://localhost:1234/v1",
        default_model="local-model",
    ),
    "openai_compatible": ProviderSpec(
        key="openai_compatible",
        label="OpenAI互換（汎用）",
        kind="openai_compatible",
        needs_api_key=False,
        api_key_optional=True,
        needs_base_url=True,
        default_base_url="",
        default_model="",
    ),
}


class AIClient(ABC):
    """Abstract base class for AI text processing."""

    @abstractmethod
    def process(self, text: str, system_prompt: Optional[str] = None) -> str:
        """Process text through the AI model (non-streaming)."""

    @abstractmethod
    def process_stream(
        self,
        text: str,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Process text through the AI model, yielding chunks as they arrive."""


class ClaudeClient(AIClient):
    """AI client using the Anthropic Claude API."""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5"):
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def process(self, text: str, system_prompt: Optional[str] = None) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt or DEFAULT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        return "".join(block.text for block in message.content if block.type == "text")

    def process_stream(
        self,
        text: str,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        with self.client.messages.stream(
            model=self.model,
            max_tokens=1024,
            system=system_prompt or DEFAULT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        ) as stream:
            for chunk in stream.text_stream:
                yield chunk


class OpenAICompatibleClient(AIClient):
    """AI client for any OpenAI-compatible Chat Completions endpoint.

    Covers OpenAI itself as well as local servers such as Ollama and LM Studio.
    Local servers usually don't require authentication, but most accept (and
    some require) an API key, so one is sent when provided.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
    ):
        import openai

        # The OpenAI SDK rejects an empty api_key, but local servers don't care
        # about its value. Fall back to a harmless placeholder when none is set.
        self.client = openai.OpenAI(
            api_key=api_key or "not-needed",
            base_url=base_url or None,
        )
        self.model = model

    def process(self, text: str, system_prompt: Optional[str] = None) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt or DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content or ""

    def process_stream(
        self,
        text: str,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt or DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class GeminiClient(AIClient):
    """AI client using the Google Gemini API."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model_name = model

    def _build_prompt(self, text: str, system_prompt: Optional[str]) -> str:
        prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        return f"{prompt}\n\n入力テキスト:\n{text}"

    def process(self, text: str, system_prompt: Optional[str] = None) -> str:
        full_prompt = self._build_prompt(text, system_prompt)
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=full_prompt,
        )
        if getattr(response, "text", None):
            return response.text
        if getattr(response, "candidates", None):
            return response.candidates[0].content.parts[0].text
        return text  # Fall back to the original text rather than losing it.

    def process_stream(
        self,
        text: str,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        full_prompt = self._build_prompt(text, system_prompt)
        try:
            response = self.client.models.generate_content_stream(
                model=self.model_name,
                contents=full_prompt,
            )
            for chunk in response:
                if getattr(chunk, "text", None):
                    yield chunk.text
        except Exception as e:
            print(f"[Gemini] Stream error: {e}", flush=True)
            # Fall back to a single non-streaming call so the user still gets output.
            result = self.process(text, system_prompt)
            if result:
                yield result


def create_ai_client(
    provider: str,
    api_key: str = "",
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> AIClient:
    """Factory creating the appropriate AI client for a provider key."""
    spec = PROVIDERS.get(provider)
    if spec is None:
        raise ValueError(f"Unknown AI provider: {provider}")

    resolved_model = model or spec.default_model
    resolved_base_url = base_url or spec.default_base_url or None

    if spec.kind == "anthropic":
        return ClaudeClient(api_key, resolved_model or "claude-haiku-4-5")
    if spec.kind == "gemini":
        return GeminiClient(api_key, resolved_model or "gemini-2.0-flash")
    if spec.kind == "openai_compatible":
        return OpenAICompatibleClient(api_key, resolved_model, resolved_base_url)

    raise ValueError(f"Unsupported provider kind: {spec.kind}")
