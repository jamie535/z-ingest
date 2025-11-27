"""Database connection management with async support."""

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy import text

from .models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connection pool and sessions."""

    def __init__(
        self,
        database_url: str | None = None,
        pool_size: int = 20,
        max_overflow: int = 10,
    ):
        """Initialize database manager.

        Args:
            database_url: PostgreSQL connection URL
            pool_size: Connection pool size
            max_overflow: Max connections beyond pool_size
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not set")

        # Convert to asyncpg driver
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        elif self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace(
                "postgres://", "postgresql+asyncpg://", 1
            )

        self.engine: AsyncEngine = create_async_engine(
            self.database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=30.0,
            echo=False,  # Set to True for SQL debugging
        )

        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def initialize(self):
        """Initialize database schema and TimescaleDB hypertables."""
        async with self.engine.begin() as conn:
            # Enable TimescaleDB extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))

            # Create all tables
            await conn.run_sync(Base.metadata.create_all)

            # Create hypertables for time-series optimization
            await conn.execute(text("""
                SELECT create_hypertable(
                    'predictions',
                    by_range('timestamp'),
                    if_not_exists => TRUE
                );
            """))

            await conn.execute(text("""
                SELECT create_hypertable(
                    'raw_samples',
                    by_range('timestamp'),
                    if_not_exists => TRUE
                );
            """))

            # Create indexes for common queries
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_predictions_session_time
                ON predictions (session_id, timestamp DESC);
            """))

            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_predictions_user_time
                ON predictions (user_id, timestamp DESC);
            """))

            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_raw_samples_user_time
                ON raw_samples (user_id, timestamp DESC);
            """))

            logger.info("Database schema initialized successfully")

    async def close(self):
        """Close database connection pool."""
        await self.engine.dispose()
        logger.info("Database connection pool closed")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session (context manager).

        Usage:
            async with db.get_session() as session:
                result = await session.execute(query)
        """
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
