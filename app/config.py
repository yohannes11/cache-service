"""Service configuration, read from environment variables.

Keeping config in one typed object means a bad value (e.g. a typo in the
database URL scheme) fails at startup instead of on the first request.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Prefix avoids clashing with unrelated env vars such as DATABASE_URL
    # that other tools on the same machine might set.
    model_config = SettingsConfigDict(env_prefix="CACHE_", env_file=".env", extra="ignore")

    # SQLite is the zero-setup default for local runs; docker-compose
    # overrides this with a PostgreSQL URL.
    database_url: str = "sqlite:///./cache.db"
    # Echo SQL to the log; handy while learning, noisy in production.
    db_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    # Cached so the environment is parsed once per process.
    return Settings()
