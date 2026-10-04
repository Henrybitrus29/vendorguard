from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"  # development | test | production
    secret_key: str = "dev-only-change-me-dev-only-change-me"
    database_url: str = "sqlite:///./app.db"
    redis_url: str = "redis://localhost:6379/0"
    queue_mode: str = "inline"  # inline (FastAPI background task) | rq (Redis worker)
    upload_dir: str = "./uploads"
    cookie_secure: bool = False  # set true when served over HTTPS
    access_token_minutes: int = 60
    max_upload_mb: int = 10
    seed_demo: bool = False  # seed fake demo data on startup if the database is empty
    app_base_url: str = ""  # e.g. https://vendorguard.example.com, used for links inside alerts

    # OCR fallback for scanned PDFs and image uploads
    ocr_enabled: bool = True
    ocr_min_chars: int = 50  # digital text shorter than this triggers OCR
    ocr_max_pages: int = 10
    ocr_page_timeout: int = 30  # seconds per page

    # Security alerts (Slack / Teams / generic webhook). Leave the URL empty to disable.
    alert_webhook_url: str = ""  # a SECRET: never commit it or log it
    alert_webhook_secret: str = ""  # optional: signs every payload with HMAC-SHA256
    alert_format: str = "slack"  # slack | teams | generic
    alert_max_per_vendor_hour: int = 5
    alert_allow_private: bool = False  # local testing only: allows http:// and private addresses

    @property
    def is_prod(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_prod and (s.secret_key.startswith("dev-only") or len(s.secret_key) < 32):
        raise RuntimeError("SECRET_KEY must be set to a random value of 32+ characters in production")
    return s
