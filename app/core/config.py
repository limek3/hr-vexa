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

    quiet_hours_enabled: bool = Field(default=False, alias="QUIET_HOURS_ENABLED")
    quiet_hours_start: str = Field(default="22:00", alias="QUIET_HOURS_START")
    quiet_hours_end: str = Field(default="09:00", alias="QUIET_HOURS_END")

    google_service_account_json: str = Field(default="", alias="GOOGLE_SERVICE_ACCOUNT_JSON")
    google_sheet_id: str = Field(default="", alias="GOOGLE_SHEET_ID")

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

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
