"""Configuration management."""

import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ingestion")

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Authentication
    edge_api_key: str = os.getenv("EDGE_API_KEY", "")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Buffer
    buffer_max_size: int = 1000

    # Persistence
    batch_size: int = 50
    flush_interval: float = 5.0


settings = Settings()
