"""Application settings loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    parser_model: str = "claude-haiku-4-5-20251001"
    categorizer_model: str = "claude-haiku-4-5-20251001"
    chat_model: str = "claude-sonnet-4-6"
    database_url: str = "sqlite:///./sente.db"
    embedding_model: str = "sentence-transformers/bge-small-en-v1.5"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
