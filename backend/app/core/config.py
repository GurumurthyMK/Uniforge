"""Application configuration via environment variables.

All secrets/configuration come from the environment. Never hardcode secrets.
See /backend/.env.example and root .env.example for local defaults.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "UniForge API"
    app_env: str = "local"  # local | dev | prod
    debug: bool = False

    api_v1_prefix: str = "/api/v1"

    # PostgreSQL connection string. Example:
    # postgresql+psycopg2://uniforge:uniforge@localhost:5432/uniforge
    database_url: str = "postgresql+psycopg2://uniforge:uniforge@localhost:5432/uniforge"

    # CORS: comma-separated origins for local dev (frontend URL).
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
