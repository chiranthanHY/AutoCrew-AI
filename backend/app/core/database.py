"""
core/database.py — Async Database Engine & Session Factory for AutoCrew AI
---------------------------------------------------------------------------
Manages the SQLAlchemy async engine and session lifecycle for Neon Serverless
PostgreSQL. Also provides helpers to initialize the PGVector extension and
LangGraph checkpoint tables.

Usage
-----
    from app.core.database import engine, get_async_session, init_db

Neon Tips
---------
- Always use ``NullPool`` or a small pool (1-5 connections) with Neon's
  serverless / pooled endpoint to avoid exhausting connection slots.
- The non-pooled direct URL should be used ONLY for schema migrations.
- Use ``connect_args={"sslmode": "require"}`` for all Neon connections.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def _get_engine_kwargs() -> dict:
    """
    Build SQLAlchemy engine kwargs optimised for Neon Serverless.

    - ``NullPool``: Disables SQLAlchemy's built-in connection pool.
      Neon's PgBouncer pooler handles pooling externally.  Using NullPool
      with the pooled Neon endpoint is the recommended pattern.
    - ``connect_args``: Passed directly to psycopg3 for SSL configuration.
    """
    connect_args: dict = {}

    if settings.is_neon:
        # Neon requires SSL; psycopg3 takes sslmode in connect_args
        connect_args["sslmode"] = settings.database_ssl_mode
        # Disable prepared statements for Neon PgBouncer compatibility
        connect_args["prepare_threshold"] = None
        logger.info("[Database] Neon detected — using NullPool + SSL mode: %s", settings.database_ssl_mode)
        return {
            "poolclass": NullPool,
            "connect_args": connect_args,
            "echo": not settings.is_production,
        }
    else:
        # Local Postgres: use a small connection pool
        return {
            "pool_size": settings.db_pool_min_size,
            "max_overflow": settings.db_pool_max_size - settings.db_pool_min_size,
            "pool_pre_ping": True,
            "connect_args": connect_args,
            "echo": not settings.is_production,
        }


engine = create_async_engine(
    settings.sqlalchemy_database_url,
    **_get_engine_kwargs(),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Session dependency (FastAPI DI)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that provides a scoped SQLAlchemy session.

    Usage::

        async with get_async_session() as session:
            result = await session.execute(...)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for injecting a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """
    Bootstrap the database on application startup.

    Actions performed:
    1. Verify the database connection is reachable.
    2. Enable the ``vector`` extension (PGVector) if not already present.
    3. Create LangGraph checkpoint tables via ``PostgresSaver.setup()``.

    This is called once from the FastAPI ``lifespan`` context manager.
    """
    from sqlalchemy import text

    logger.info("[Database] Initialising database connection...")

    try:
        async with engine.connect() as conn:
            # 1. Ping the database
            await conn.execute(text("SELECT 1"))
            logger.info("[Database] ✓ Connection established.")

            # 2. Enable PGVector extension
            await conn.execute(
                text("CREATE EXTENSION IF NOT EXISTS vector;")
            )
            await conn.commit()
            logger.info("[Database] ✓ PGVector extension enabled.")

    except Exception as exc:
        logger.error("[Database] ✗ Initialisation failed: %s", exc, exc_info=True)
        raise


async def check_db_health() -> dict:
    """
    Perform a quick database health check.

    Returns:
        dict with ``status`` (ok/error), ``latency_ms``, and optional ``error``.
    """
    import time
    from sqlalchemy import text

    start = time.monotonic()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency = round((time.monotonic() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency}
    except Exception as exc:
        latency = round((time.monotonic() - start) * 1000, 2)
        return {"status": "error", "latency_ms": latency, "error": str(exc)}
