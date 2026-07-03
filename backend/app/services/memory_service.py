"""
services/memory_service.py — Long-Term Memory (RAG) for AutoCrew AI
---------------------------------------------------------------------
Stores task summaries as vector embeddings in Neon PostgreSQL (pgvector).
On each new task, retrieves semantically similar past tasks to inject
as context into the Executor agent — giving the system "institutional memory".

Vector Store: langchain_postgres.PGVector
Embeddings:   langchain_community HuggingFace (all-MiniLM-L6-v2, runs locally, free)
              Falls back to simple keyword-based retrieval if embeddings fail.

Table: autocrew_memories (auto-created by PGVector.from_existing_index or .from_documents)
"""

import logging
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding model initialisation
# ---------------------------------------------------------------------------

_embeddings = None

def _get_embeddings():
    """Lazy-load the embedding model. Returns None if unavailable."""
    global _embeddings
    if _embeddings is not None:
        return _embeddings
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info("[MemoryService] ✓ HuggingFace embeddings loaded (all-MiniLM-L6-v2).")
        return _embeddings
    except Exception as exc:
        logger.warning("[MemoryService] Could not load HuggingFace embeddings: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Vector store helper
# ---------------------------------------------------------------------------

_COLLECTION_NAME = "autocrew_memories"

def _get_vector_store():
    """
    Return a PGVector vector store connected to Neon.
    Creates the collection table if it doesn't exist.
    Returns None if unavailable.
    """
    embeddings = _get_embeddings()
    if embeddings is None:
        return None
    try:
        from langchain_postgres import PGVector
        # Use the synchronous connection string (psycopg2) for PGVector
        conn_str = settings.postgres_url
        # PGVector from langchain_postgres uses psycopg3 driver string
        # Make sure it's properly formed
        vector_store = PGVector(
            embeddings=embeddings,
            collection_name=_COLLECTION_NAME,
            connection=conn_str,
            use_jsonb=True,
        )
        return vector_store
    except Exception as exc:
        logger.warning("[MemoryService] Could not initialise PGVector store: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def retrieve_relevant_memories(task: str, k: int = 3) -> Optional[str]:
    """
    Retrieve the top-k most semantically similar past task summaries.

    Args:
        task: The current user task string.
        k: Number of past memories to retrieve.

    Returns:
        A formatted string of relevant memories for injection into prompts,
        or None if no memories exist or the service is unavailable.
    """
    try:
        vector_store = _get_vector_store()
        if vector_store is None:
            return None

        results = vector_store.similarity_search(task, k=k)
        if not results:
            return None

        memory_lines = []
        for i, doc in enumerate(results, 1):
            meta = doc.metadata or {}
            score_label = meta.get("score_label", "")
            task_preview = meta.get("original_task", "")[:100]
            memory_lines.append(
                f"**Past Task {i}** ({score_label}): {task_preview}\n"
                f"Summary: {doc.page_content[:400]}"
            )

        context = "\n\n".join(memory_lines)
        logger.info("[MemoryService] Retrieved %d relevant memories.", len(results))
        return context

    except Exception as exc:
        logger.warning("[MemoryService] retrieve_relevant_memories failed: %s", exc)
        return None


async def store_task_memory(
    task_id: str,
    task: str,
    final_output: str,
    critique_score: float,
    iteration: int,
) -> bool:
    """
    Store a completed task summary as a vector embedding for future retrieval.

    Called after task completion (in the verifier node or final SSE event).

    Args:
        task_id: Unique task UUID.
        task: Original task string.
        final_output: The polished final output from the Verifier.
        critique_score: The final quality score.
        iteration: Number of revision loops taken.

    Returns:
        True if stored successfully, False otherwise.
    """
    try:
        vector_store = _get_vector_store()
        if vector_store is None:
            return False

        from langchain_core.documents import Document

        # Summarise output to 500 chars for the embedding text
        output_summary = final_output[:500].strip()
        score_label = "excellent" if critique_score >= 8 else "good" if critique_score >= 6 else "fair"

        doc = Document(
            page_content=output_summary,
            metadata={
                "task_id": task_id,
                "original_task": task[:200],
                "critique_score": critique_score,
                "score_label": score_label,
                "iterations": iteration,
            },
        )

        vector_store.add_documents([doc])
        logger.info(
            "[MemoryService] ✓ Stored memory for task_id=%s (score=%.1f).",
            task_id,
            critique_score,
        )
        return True

    except Exception as exc:
        logger.warning("[MemoryService] store_task_memory failed: %s", exc)
        return False


async def list_memories(limit: int = 20) -> List[dict]:
    """
    Return a list of stored memory summaries (for the /memory endpoint).

    Args:
        limit: Maximum records to return.

    Returns:
        List of dicts with task_id, original_task, critique_score, score_label.
    """
    try:
        from app.core.database import engine
        from sqlalchemy import text

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT
                        cmetadata->>'task_id'        AS task_id,
                        cmetadata->>'original_task'  AS original_task,
                        cmetadata->>'critique_score' AS critique_score,
                        cmetadata->>'score_label'    AS score_label,
                        cmetadata->>'iterations'     AS iterations,
                        document                     AS summary
                    FROM langchain_pg_embedding
                    WHERE collection_id = (
                        SELECT uuid FROM langchain_pg_collection
                        WHERE name = :collection
                    )
                    ORDER BY ctid DESC
                    LIMIT :limit
                    """
                ),
                {"collection": _COLLECTION_NAME, "limit": limit},
            )
            rows = result.mappings().all()
            return [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("[MemoryService] list_memories failed: %s", exc)
        return []
