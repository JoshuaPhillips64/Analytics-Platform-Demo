"""Runtime settings for the EL layer, loaded from environment / .env.

Secrets never live in git (golden rule #10): set them in a gitignored .env or
via real environment variables (e.g. the EC2 IAM role supplies AWS creds; the DB
password comes from the environment, not source).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Alpha Vantage ---
    alpha_vantage_api_key: str = Field(..., description="Alpha Vantage API key")
    av_base_url: str = "https://www.alphavantage.co/query"
    # Premium tier = 75 req/min; free = 5/min. Drives the client's min interval.
    av_requests_per_minute: int = 75
    av_request_timeout_s: int = 30
    av_max_retries: int = 5
    av_rate_limit_backoff_s: int = 60

    # --- S3 raw archive ---
    s3_bucket: str = Field(..., description="Raw-archive S3 bucket name")
    aws_region: str | None = None

    # --- RDS Postgres ---
    db_host: str = Field(..., description="RDS hostname")
    db_port: int = 5432
    db_name: str = "equities"
    db_user: str = "dbt"
    db_password: str = Field(..., description="DB password")
    db_sslmode: str = "require"

    @property
    def min_interval_s(self) -> float:
        """Minimum seconds between API calls, derived from the rate limit."""
        return 60.0 / max(self.av_requests_per_minute, 1)

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?sslmode={self.db_sslmode}"
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton (read once per process)."""
    return Settings()  # type: ignore[call-arg]
