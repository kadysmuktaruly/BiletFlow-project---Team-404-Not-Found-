"""Settings, read from environment / `.env`. See `.env.example` at the repo root."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# `.env` lives at the repo root, but the API is usually run from `apps/api`. A bare
# `env_file=".env"` resolves against the working directory and silently reads nothing,
# so both locations are listed explicitly; the later file wins where they overlap.
_API_DIR = Path(__file__).resolve().parent.parent
_ENV_FILES = (_API_DIR.parent.parent / ".env", _API_DIR / ".env")

# Only these environments may run with the built-in development JWT secret.
_DEV_ENVIRONMENTS = frozenset({"development", "test"})
_DEV_JWT_SECRET = "dev-only-insecure-jwt-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

    # Async driver throughout. Never a sync `postgresql://` URL — mixing sync and async
    # sessions in one process is the trap this project is explicitly avoiding.
    database_url: str = "postgresql+asyncpg://biletflow:biletflow@localhost:5433/biletflow"

    app_name: str = "BiletFlow API"
    environment: str = "development"
    # The web app's origin. Email links (verify, reset) point here, and it is the default
    # CORS origin.
    public_base_url: str = "http://localhost:3000"
    # Extra CORS origins, comma-separated. Empty means "just public_base_url".
    cors_origins: str = ""

    # SRS 4.1 auth. The secret has a development default only; see the validator below.
    jwt_secret: str = _DEV_JWT_SECRET
    jwt_access_ttl_seconds: int = 900
    jwt_refresh_ttl_seconds: int = 60 * 60 * 24 * 30
    email_verify_ttl_seconds: int = 60 * 60 * 24
    password_reset_ttl_seconds: int = 60 * 60
    # The refresh cookie's Secure flag. Off for http://localhost, on everywhere else.
    cookie_secure: bool = False

    # SRS 4.10 transactional email. Mailpit in development.
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "BiletFlow <no-reply@biletflow.local>"

    # SRS 4.3.1: a seat hold expires and releases the seat when checkout is abandoned.
    seat_hold_ttl_seconds: int = 600

    # SRS 3.3: one-time fee per event, in whole KZT. Amount is an open decision (SRS 12);
    # this is a placeholder for the demonstration.
    activation_fee_kzt: int = 5000

    # SRS 4.6 / 4.14: the currency for the initial Kazakhstan release.
    currency: str = "KZT"

    @field_validator("jwt_secret", mode="before")
    @classmethod
    def _empty_secret_means_unset(cls, value: object) -> object:
        # `.env.example` ships `JWT_SECRET=` (empty). Treat that as "not set" rather than
        # as an empty signing key.
        return _DEV_JWT_SECRET if value in ("", None) else value

    @model_validator(mode="after")
    def _require_real_secret_outside_dev(self) -> "Settings":
        if self.environment not in _DEV_ENVIRONMENTS and (
            self.jwt_secret == _DEV_JWT_SECRET or len(self.jwt_secret) < 32
        ):
            raise ValueError(
                "JWT_SECRET must be set to a random value of at least 32 characters "
                f"when ENVIRONMENT={self.environment!r}"
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        extra = [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]
        return list(dict.fromkeys([self.public_base_url.rstrip("/"), *extra]))

    @property
    def sync_database_url(self) -> str:
        """Alembic's offline mode and some tooling want a non-async URL."""
        return self.database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
