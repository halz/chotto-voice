"""Server configuration using pydantic-settings."""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Server settings loaded from environment variables."""
    
    # Server
    app_name: str = "Chotto Voice"
    debug: bool = False
    secret_key: str  # JWT signing key
    
    # Google OAuth
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    
    # Turso Database
    turso_db_url: str
    turso_auth_token: str
    
    # OpenAI (for Whisper)
    openai_api_key: str
    
    # Stripe (billing)
    stripe_secret_key: str
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""  # Price ID for credit packs
    
    # Usage limits
    free_credits: int = 100  # Free credits on signup
    credit_per_minute: int = 1  # Credits per minute of transcription
    
    # CORS
    allowed_origins: list[str] = ["http://localhost", "https://chotto.voice"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
