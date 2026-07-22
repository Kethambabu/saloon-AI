"""Application configuration management using environment variables."""

from functools import lru_cache
import os
from typing import List, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Placeholder value shipped in source control — must never be used in production,
#: since it would let anyone forge valid JWTs (see validate_secret_key_startup()).
INSECURE_DEFAULT_SECRET_KEY = "your-secret-key-change-in-production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = Field(default="SalonAI Workforce API", alias="APP_NAME")
    app_version: str = Field(default="0.1.0")
    debug: bool = Field(default=False, alias="DEBUG")
    environment: str = Field(default="development", alias="ENVIRONMENT")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_testing(self) -> bool:
        return self.environment.lower() == "testing"

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in ("development", "dev")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    api_prefix: str = Field(default="/api/v1")

    # Database
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")
    
    # Redis configuration
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")


    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")

    # Security & CORS
    secret_key: str = Field(
        default=INSECURE_DEFAULT_SECRET_KEY,
        alias="SECRET_KEY"
    )
    cors_origins: Union[List[str], str] = Field(
        default=[
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:3000",
        ],
        alias="CORS_ORIGINS",
    )
    cors_allow_credentials: bool = Field(default=True)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                return json.loads(v)
            return [x.strip() for x in v.split(",") if x.strip()]
        return v
    
    # External Services
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    groq_model: Optional[str] = Field(default=None, alias="GROQ_MODEL")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    supabase_url: Optional[str] = Field(default=None, alias="SUPABASE_URL")
    supabase_anon_key: Optional[str] = Field(default=None, alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: Optional[str] = Field(default=None, alias="SUPABASE_SERVICE_ROLE_KEY")
    max_prompt_tokens: int = Field(default=4500, alias="MAX_PROMPT_TOKENS")

    # Hugging Face LLM Configuration
    huggingface_enabled: bool = Field(default=True, alias="HUGGINGFACE_ENABLED")
    huggingface_model: str = Field(default="Qwen/Qwen2.5-72B-Instruct", alias="HUGGINGFACE_MODEL")
    huggingface_api_base_url: str = Field(default="https://router.huggingface.co/v1", alias="HUGGINGFACE_API_BASE_URL")
    huggingface_api_key: Optional[str] = Field(default=None, alias="HUGGINGFACE_API_KEY")

    # Features
    enable_rag: bool = Field(default=True, alias="ENABLE_RAG")
    enable_agents: bool = Field(default=True, alias="ENABLE_AGENTS")

    @property
    def data_dir(self) -> str:
        # Resolves to project backend/data directory
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(backend_dir, "data")

    model_config = SettingsConfigDict(
        env_file=(
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
            ".env"
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def validate_secret_key_startup(settings_obj: Optional["Settings"] = None) -> bool:
    """
    Refuse to treat startup as valid if running in production with the
    insecure placeholder SECRET_KEY still in place — that value is public
    (shipped in source control), so leaving it in production lets anyone
    forge valid JWTs for any user/role.
    """
    s = settings_obj or get_settings()
    if s.is_production and s.secret_key == INSECURE_DEFAULT_SECRET_KEY:
        return False
    return True


# Export settings instance
settings = get_settings()

