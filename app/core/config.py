import os
import secrets
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings for Levorify Sovereign D2C Platform.
    Loads configurations from environment variables or .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Project Metadata
    PROJECT_NAME: str = "Levorify Sovereign D2C Commerce API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Database Configuration (PostgreSQL Async default with SQLite fallback for instant onboarding)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/levorify_db"
    # Set to True to allow automatic SQLite local fallback if PostgreSQL is unreachable during dev
    FALLBACK_TO_SQLITE_IN_DEV: bool = True
    SQLITE_URL: str = "sqlite+aiosqlite:///./levorify.db"

    # Security & JWT Settings
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "levorify-hyper-secure-secret-key-change-in-production-9a8b7c6d")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # BYOK (Bring Your Own Key) Symmetric Key Encryption (Fernet 32-byte base64)
    # Never store user Gemini / AI keys in plaintext!
    BYOK_ENCRYPTION_KEY: str = os.getenv(
        "BYOK_ENCRYPTION_KEY",
        # Default 32 url-safe base64-encoded bytes for seamless zero-setup dev runs
        "VTBHNVV2Q3pYcm05V1pPblNYc0k3ZDRqWkZreFk1Wng="
    )

    # CORS Allowed Origins
    BACKEND_CORS_ORIGINS: List[str] = [
        "*",
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://levorify.com",
        "https://app.levorify.com",
    ]

    # Google Gemini Direct Integration Defaults
    DEFAULT_GEMINI_MODEL: str = "gemini-1.5-flash"


settings = Settings()
