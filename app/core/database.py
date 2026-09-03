import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

logger = logging.getLogger("levorify.database")

# Base Declarative Model with AsyncAttrs support for SQLAlchemy 2.0
class Base(AsyncAttrs, DeclarativeBase):
    pass


# Primary Engine Configuration
def create_app_engine(db_url: str):
    connect_args = {}
    if "sqlite" in db_url:
        connect_args["check_same_thread"] = False

    return create_async_engine(
        db_url,
        echo=False,
        future=True,
        connect_args=connect_args,
        pool_pre_ping=True,
    )


# Active engine and sessionmaker
engine = create_app_engine(settings.DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """
    Verify database connection and initialize tables.
    Includes graceful SQLite fallback in dev mode if PostgreSQL is not running.
    """
    global engine, AsyncSessionLocal

    try:
        async with engine.begin() as conn:
            # Import models dynamically to ensure they are registered with Base.metadata
            import app.models  # noqa: F401
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database schemas successfully synchronized.")
    except Exception as exc:
        if settings.FALLBACK_TO_SQLITE_IN_DEV and "postgresql" in settings.DATABASE_URL:
            logger.warning(
                f"PostgreSQL connection to {settings.DATABASE_URL} failed ({exc}). "
                f"Falling back to local SQLite engine ({settings.SQLITE_URL}) for development."
            )
            engine = create_app_engine(settings.SQLITE_URL)
            AsyncSessionLocal = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
            async with engine.begin() as conn:
                import app.models  # noqa: F401
                await conn.run_sync(Base.metadata.create_all)
                logger.info("SQLite local database schemas successfully initialized.")
        else:
            logger.error(f"Fatal database initialization error: {exc}")
            raise exc


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session per request.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
