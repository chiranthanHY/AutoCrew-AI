"""
setup_neon.py — One-shot Neon Database Setup Script for AutoCrew AI
--------------------------------------------------------------------
Run this ONCE after creating your Neon project to:
  1. Verify the database connection
  2. Enable the PGVector extension
  3. Create LangGraph checkpoint tables (via PostgresSaver.setup())

Usage:
  cd backend
  python setup_neon.py

Prerequisites:
  - .env file with DATABASE_URL set to your Neon connection string
  - pip install -r requirements.txt

IMPORTANT: Use the DIRECT (non-pooled) connection URL for this script,
not the pooled endpoint. Schema migrations require a direct connection.
Set DATABASE_URL to the direct connection string before running this.
"""

import logging
import sys
import os

# ── Bootstrap path so we can import app modules ──────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_setup():
    from app.core.config import settings

    logger.info("=" * 60)
    logger.info("  AutoCrew AI — Neon Database Setup")
    logger.info("=" * 60)
    logger.info("  DATABASE_URL : %s", settings.database_url[:60] + "...")
    logger.info("  Is Neon      : %s", settings.is_neon)
    logger.info("  SSL Mode     : %s", settings.database_ssl_mode)
    logger.info("  Postgres URL : %s", settings.postgres_url[:60] + "...")
    logger.info("=" * 60)

    # ── Step 1: Test basic connectivity ───────────────────────────────────
    logger.info("\n[1/3] Testing database connection...")
    try:
        import psycopg
        with psycopg.connect(settings.postgres_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                row = cur.fetchone()
                logger.info("  ✓ Connected: %s", row[0][:80])
    except Exception as exc:
        logger.error("  ✗ Connection failed: %s", exc)
        logger.error("  Check your DATABASE_URL in .env")
        sys.exit(1)

    # ── Step 2: Enable PGVector ────────────────────────────────────────────
    logger.info("\n[2/3] Enabling PGVector extension...")
    try:
        import psycopg
        with psycopg.connect(settings.postgres_url) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                logger.info("  ✓ PGVector extension enabled (or already present).")
    except Exception as exc:
        logger.warning("  ⚠ PGVector extension error: %s", exc)
        logger.warning("  PGVector is optional — LangGraph checkpointing will still work.")

    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        with PostgresSaver.from_conn_string(settings.postgres_url) as checkpointer:
            checkpointer.setup()
        logger.info("  ✓ Checkpoint tables created successfully.")
    except Exception as exc:
        logger.error("  ✗ Checkpoint table creation failed: %s", exc)
        logger.error("  Ensure 'langgraph-checkpoint-postgres' is installed.")
        sys.exit(1)

    # ── Done ──────────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("  ✅ Neon database setup complete!")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("  1. Switch to the POOLED connection string in .env")
    logger.info("     (use -pooler.neon.tech endpoint for app traffic)")
    logger.info("  2. Start the backend: uvicorn app.main:app --reload")
    logger.info("  3. Test: curl http://localhost:8000/health")
    logger.info("")


if __name__ == "__main__":
    run_setup()
