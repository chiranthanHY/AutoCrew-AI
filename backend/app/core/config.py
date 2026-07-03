"""
core/config.py — Application Settings for AutoCrew AI
-------------------------------------------------------
Neon Serverless PostgreSQL + PGVector edition.

All configuration is read from environment variables (or a .env file).
Access settings anywhere via: ``from app.core.config import settings``

Neon DB notes
-------------
- Neon requires ``sslmode=require`` (or ``verify-full`` in prod).
- Use the **pooled** connection string for application traffic
  (port 5432, hostname ends with ``-pooler.neon.tech``).
- Use the **direct** (non-pooled) string only for migrations and setup.
- LangGraph's PostgresSaver works with both psycopg2 (sync) and psycopg3
  (async). The ``postgres_url`` and ``postgres_async_url`` properties
  return correctly formatted DSNs for each driver.
"""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralised, type-safe application settings powered by Pydantic v2.

    All fields are automatically populated from environment variables or
    a ``.env`` file in the working directory. Field names are
    case-insensitive (e.g. ``GROQ_API_KEY`` → ``groq_api_key``).
    """

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    project_name: str = "AutoCrew AI"
    environment: str = "development"

    # Safety valve: absolute maximum Critic→Executor revision loops
    max_iterations: int = 5

    # Critic score (0–10) below which the draft loops back to Executor
    critic_approval_threshold: float = 8.0

    # ------------------------------------------------------------------
    # LLM — Groq (Primary)
    # ------------------------------------------------------------------
    groq_api_key: str = ""

    # Primary model for Planner / Executor / Critic / Verifier
    groq_model_name: str = "llama-3.1-70b-versatile"

    # Faster / cheaper model for lightweight tasks (query generation etc.)
    groq_fast_model_name: str = "llama3-8b-8192"

    # LLM temperature (0 = deterministic, 1 = creative)
    groq_temperature: float = 0.2

    # ------------------------------------------------------------------
    # Tools — Tavily
    # ------------------------------------------------------------------
    tavily_api_key: Optional[str] = None

    # ------------------------------------------------------------------
    # Database — Neon Serverless PostgreSQL
    # ------------------------------------------------------------------
    # Set this to your Neon connection string (pooled or direct).
    # Neon format: postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/dbname?sslmode=require
    #
    # If DATABASE_URL is set, it takes precedence over individual fields.
    # For local Postgres, use: postgresql://user:pass@localhost:5432/autocrew
    database_url: str = (
        "postgresql://autocrew:autocrew@localhost:5432/autocrew"
    )

    # SSL mode: "require" for Neon production, "disable" for local dev
    # Override via DATABASE_SSL_MODE env var
    database_ssl_mode: str = "prefer"

    # Neon-specific: connection pool settings
    # (psycopg_pool is used to maintain persistent connections to serverless Neon)
    db_pool_min_size: int = 1
    db_pool_max_size: int = 10

    # ------------------------------------------------------------------
    # Observability — LangSmith
    # ------------------------------------------------------------------
    langchain_tracing_v2: str = "false"
    langchain_api_key: Optional[str] = None
    langchain_project: str = "autocrew_ai"

    # ------------------------------------------------------------------
    # Pydantic-settings config
    # ------------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def is_production(self) -> bool:
        """Return True when running in a production environment."""
        return self.environment.lower() == "production"

    @property
    def is_neon(self) -> bool:
        """Return True if the DATABASE_URL points to a Neon endpoint."""
        return "neon.tech" in self.database_url

    @property
    def postgres_url(self) -> str:
        """
        Synchronous psycopg2 DSN for LangGraph's PostgresSaver (sync variant).

        - Strips SQLAlchemy prefixes (``postgresql+psycopg2://`` → ``postgresql://``)
        - Appends ``sslmode`` if the URL doesn't already have it and we're on Neon.
        - Compatible with ``PostgresSaver.from_conn_string()``.
        """
        url = self.database_url
        # Strip SQLAlchemy driver prefixes
        for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://"):
            url = url.replace(prefix, "postgresql://", 1)

        # Ensure SSL for Neon connections
        if self.is_neon and "sslmode=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}sslmode={self.database_ssl_mode}"

        return url

    @property
    def postgres_async_url(self) -> str:
        """
        Async psycopg3 DSN for ``AsyncPostgresSaver`` (LangGraph async checkpointer).

        psycopg3 uses ``postgresql+psycopg://`` driver prefix when used with
        SQLAlchemy, but the raw DSN for direct psycopg3 use is simply
        ``postgresql://`` — which is the same as ``postgres_url``.
        """
        return self.postgres_url

    @property
    def sqlalchemy_database_url(self) -> str:
        """
        SQLAlchemy-compatible async URL using psycopg3 async driver.
        Used by ``create_async_engine``.
        """
        url = self.database_url
        # Ensure we're using the async psycopg3 driver
        if url.startswith("postgresql://") or url.startswith("postgres://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql+psycopg2://"):
            url = url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)

        # Add SSL args for Neon if not present
        if self.is_neon and "sslmode=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}sslmode={self.database_ssl_mode}"

        return url

    @property
    def sqlalchemy_sync_url(self) -> str:
        """SQLAlchemy sync URL using psycopg2 (for migrations etc.)."""
        url = self.database_url
        if url.startswith("postgresql://") or url.startswith("postgres://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        if self.is_neon and "sslmode=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}sslmode={self.database_ssl_mode}"
        return url


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------
settings = Settings()
