"""Application configuration loaded from environment variables."""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""

    # Database - Railway provides DATABASE_URL for Postgres
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./solpnl.db")

    # Helius API
    helius_api_key: str = ""

    # Anthropic Claude API (for fraud detection)
    anthropic_api_key: Optional[str] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Strip whitespace and newlines from API keys
        if self.anthropic_api_key:
            self.anthropic_api_key = self.anthropic_api_key.strip().replace('\n', '').replace('\r', '')
        if self.helius_api_key:
            self.helius_api_key = self.helius_api_key.strip().replace('\n', '').replace('\r', '')

    # Optional APIs
    solscan_api_key: Optional[str] = None

    # Redis (for caching and rate limiting)
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Server
    host: str = "0.0.0.0"
    port: int = int(os.getenv("PORT", "8000"))

    # CORS - Allow Vercel frontend URLs
    cors_origins: list = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.vercel.app",
    ]

    # Frontend URL (for CORS in production)
    frontend_url: Optional[str] = os.getenv("FRONTEND_URL")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

# Add frontend URL to CORS if set
if settings.frontend_url:
    settings.cors_origins.append(settings.frontend_url)

# Log configuration (mask sensitive data)
from loguru import logger
logger.info(f"ANTHROPIC_API_KEY loaded: {bool(settings.anthropic_api_key)}")
if settings.anthropic_api_key:
    logger.info(f"ANTHROPIC_API_KEY prefix: {settings.anthropic_api_key[:10]}...")
else:
    logger.warning("ANTHROPIC_API_KEY is NOT set!")
