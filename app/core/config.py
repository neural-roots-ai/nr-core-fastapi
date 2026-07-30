from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    ENVIRONMENT: str = "development"

    # --- Database ---
    POSTGRES_DB_USERNAME: str
    POSTGRES_DB_PASSWORD: str
    POSTGRES_DB_HOST: str
    POSTGRES_DB_PORT: int = 5432
    POSTGRES_DB_NAME: str = "NRDB"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # --- JWT ---
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PBKDF2_ITERATIONS: int = 600_000

    # --- SMTP ---
    SMTP_SERVER: str
    SMTP_PORT: int = 465
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    EMAIL_FROM_NAME: str = "Neural Roots"
    EMAIL_FROM_ADDRESS: str | None = None

    # --- OTP ---
    OTP_LENGTH: int = 6
    OTP_EXPIRE_MINUTES: int = 10
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_MAX_ATTEMPTS: int = 5

    # --- Account lockout ---
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15

    # --- Razorpay ---
    RAZORPAY_KEY_ID: str
    RAZORPAY_KEY_SECRET: str
    RAZORPAY_WEBHOOK_SECRET: str
    DEFAULT_CURRENCY: str = "INR"

    # --- CORS ---
    # Kept as a raw comma-separated string (not list[str]): pydantic-settings
    # tries to JSON-decode env values for complex/list-typed fields before
    # any validator runs, which breaks on a plain "http://a,http://b" value.
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        password = quote_plus(self.POSTGRES_DB_PASSWORD)
        return (
            f"postgresql+asyncpg://{self.POSTGRES_DB_USERNAME}:{password}"
            f"@{self.POSTGRES_DB_HOST}:{self.POSTGRES_DB_PORT}/{self.POSTGRES_DB_NAME}"
        )

    @property
    def email_from(self) -> str:
        return self.EMAIL_FROM_ADDRESS or self.SMTP_USERNAME


@lru_cache
def get_settings() -> Settings:
    return Settings()
