"""Application configuration settings using environment variables."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "SalonAI Workforce"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"  # development, staging, production

    # Server
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    api_prefix: str = "/api/v1"

    # Database
    database_url: Optional[str] = None
    database_echo: bool = False

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json or text

    # Security
    secret_key: str = "your-secret-key-change-in-production"
    cors_origins: list = ["http://localhost:5173", "http://localhost:3000"]
    
    # External Services
    openai_api_key: Optional[str] = None
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export settings instance
settings = get_settings()
