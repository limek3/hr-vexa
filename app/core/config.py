from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(default="", alias="BOT_TOKEN")
    bot_proxy_url: str = Field(default="", alias="BOT_PROXY_URL")

    database_url_raw: str = Field(default="", alias="DATABASE_URL")

    telegram_api_id: int | None = Field(default=None, alias="TELEGRAM_API_ID")
    telegram_api_hash: str = Field(default="", alias="TELEGRAM_API_HASH")
    telegram_session_string: str = Field(default="", alias="TELEGRAM_SESSION_STRING")
    telegram_auto_join_sources: bool = Field(default=True, alias="TELEGRAM_AUTO_JOIN_SOURCES")
    telegram_source_refresh_interval_seconds: int = Field(
        default=60,
        alias="TELEGRAM_SOURCE_REFRESH_INTERVAL_SECONDS",
    )
    telegram_join_delay_seconds: int = Field(default=12, alias="TELEGRAM_JOIN_DELAY_SECONDS")
    telegram_max_joins_per_cycle: int = Field(default=2, alias="TELEGRAM_MAX_JOINS_PER_CYCLE")

    max_sources_per_search: int = Field(default=10, alias="MAX_SOURCES_PER_SEARCH")

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    admin_telegram_ids: str = Field(default="", alias="ADMIN_TELEGRAM_IDS")

    notification_delivery_retention_days: int = Field(
        default=30,
        alias="NOTIFICATION_DELIVERY_RETENTION_DAYS",
    )

    @property
    def sync_database_url(self) -> str:
        if not self.database_url_raw:
            raise RuntimeError("DATABASE_URL is required")
        return _normalize_database_url(self.database_url_raw, async_driver=False)

    @property
    def database_url(self) -> str:
        if not self.database_url_raw:
            raise RuntimeError("DATABASE_URL is required")
        return _normalize_database_url(self.database_url_raw, async_driver=True)

    @property
    def admin_ids(self) -> set[int]:
        ids: set[int] = set()
        for raw_token in self.admin_telegram_ids.replace(";", ",").split(","):
            token = raw_token.strip()
            if not token:
                continue
            try:
                ids.add(int(token))
            except ValueError:
                continue
        return ids


def _normalize_database_url(raw_url: str, *, async_driver: bool) -> str:
    url = raw_url.strip()
    if async_driver:
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
