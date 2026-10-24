"""Local/test configuration only; never load environment files implicitly."""

import os
from dataclasses import dataclass, field

from sqlalchemy.engine import make_url


def get_log_level() -> str:
    level = os.environ.get("LOG_LEVEL", "INFO")
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise RuntimeError("Invalid LOG_LEVEL configuration")
    return level


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str = field(repr=False)
    otp_hash_key: bytes = field(repr=False)
    log_level: str


def load_settings() -> Settings:
    level = get_log_level()
    environment = os.environ.get("APP_ENV")
    if environment not in {"local", "test"}:
        raise RuntimeError("APP_ENV must explicitly select local or test")
    database_url = os.environ.get("DATABASE_URL", "")
    try:
        url = make_url(database_url)
        valid = (
            url.drivername == "postgresql+psycopg"
            and url.host in {"127.0.0.1", "localhost", "::1", "db"}
            and url.database == f"experience_{environment}"
            and bool(url.username and url.password)
            and not url.query
        )
    except Exception:
        valid = False
    if not valid:
        raise RuntimeError("Invalid local/test DATABASE_URL configuration") from None
    key = os.environ.get("OTP_HASH_KEY", "").encode()
    if len(key) < 32:
        raise RuntimeError("OTP_HASH_KEY must contain at least 32 bytes")
    return Settings(environment, database_url, key, level)
