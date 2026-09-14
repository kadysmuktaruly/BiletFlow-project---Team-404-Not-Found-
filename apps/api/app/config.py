"""Settings, read from environment / `.env`. See `.env.example` at the repo root."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Async driver throughout. Never a sync `postgresql://` URL — mixing sync and async
    # sessions in one process is the trap this project is explicitly avoiding.
    database_url: str = "postgresql+asyncpg://biletflow:biletflow@localhost:5432/biletflow"

    app_name: str = "BiletFlow API"
    environment: str = "development"
    public_base_url: str = "http://localhost:3000"

    # SRS 4.3.1: a seat hold expires and releases the seat when checkout is abandoned.
    seat_hold_ttl_seconds: int = 600

    # SRS 3.3: one-time fee per event, in whole KZT. Amount is an open decision (SRS 12);
    # this is a placeholder for the demonstration.
    activation_fee_kzt: int = 5000

    # SRS 4.6 / 4.14: the currency for the initial Kazakhstan release.
    currency: str = "KZT"

    @property
    def sync_database_url(self) -> str:
        """Alembic's offline mode and some tooling want a non-async URL."""
        return self.database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
