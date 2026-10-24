from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    ENV: str = "development"  # development | production | test
    APP_NAME: str = "IntelliMetrics AI"
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'storage' / 'intellimetrics.db').as_posix()}"
    REDIS_URL: str = "redis://localhost:6379/0"
    USE_CELERY: bool = False  # false -> in-process background thread (local dev without Redis)
    SECRET_KEY: str = "dev-secret-change-me-please-use-a-long-random-string"
    ENCRYPTION_KEY: str = ""  # Fernet key; derived from SECRET_KEY when empty
    ACCESS_TTL_MIN: int = 15
    REFRESH_TTL_DAYS: int = 7
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    FRONTEND_URL: str = "http://localhost:5173"
    DATA_DIR: str = str(BASE_DIR / "storage" / "datasets")
    MAX_UPLOAD_MB: int = 500
    QUERY_TIMEOUT_SECONDS: int = 20
    QUERY_ROW_LIMIT: int = 10000
    RATE_LIMIT_ENABLED: bool = True
    AUTH_RATE_LIMIT: int = 20  # requests per minute per IP on auth routes
    AI_PROVIDER: str = "none"  # openai | gemini | none
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    AI_TIMEOUT_SECONDS: int = 25
    AUTO_SEED: bool = False

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.ENV in ("development", "test")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
