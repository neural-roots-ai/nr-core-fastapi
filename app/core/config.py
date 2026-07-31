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
    # Currencies this Razorpay account can actually charge/settle in. Stays
    # INR-only until an international/multi-currency Razorpay approval is in
    # place - see README "Multi-currency pricing". A currency outside this
    # list is still shown to the browsing user (display price), but the real
    # Razorpay order/checkout falls back to SETTLEMENT_CURRENCY.
    RAZORPAY_CHARGE_CURRENCIES: str = "INR"
    SETTLEMENT_CURRENCY: str = "INR"

    # --- Regional pricing / currency detection ---
    # Currency shown to a visitor whose region can't be resolved to a known
    # currency (no geo signal, unmapped country, ...).
    DEFAULT_CURRENCY: str = "USD"
    # Trust an edge/CDN-injected country header (Cloudflare, CloudFront,
    # Fastly, ...) before falling back to a local GeoIP database. Zero extra
    # latency/infra when the app already sits behind such a CDN.
    TRUST_CDN_COUNTRY_HEADER: bool = True
    CDN_COUNTRY_HEADER_NAME: str = "cf-ipcountry"
    # Optional local MaxMind GeoLite2-Country.mmdb path, used only when the
    # CDN header above is absent/untrusted. Geo-detection degrades to
    # Accept-Language, then DEFAULT_CURRENCY, if this isn't configured or the
    # `geoip2` package isn't installed - never a hard dependency.
    GEOIP_DB_PATH: str | None = None
    # How long a resolved country->currency mapping is cached in-process
    # before being re-read from the DB (the mapping changes rarely).
    CURRENCY_MAP_CACHE_TTL_SECONDS: int = 300
    PREFERRED_CURRENCY_COOKIE_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 180  # 180 days

    @property
    def razorpay_charge_currencies(self) -> set[str]:
        return {c.strip().upper() for c in self.RAZORPAY_CHARGE_CURRENCIES.split(",") if c.strip()}

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
