"""
main.py — FastAPI Application Entry Point for AutoCrew AI
----------------------------------------------------------
Neon Serverless PostgreSQL + LangGraph Async edition.

HTTP API surface:
  GET  /health                        → Service + DB health check
  POST /tasks/run                     → Stream a new task via SSE
  POST /tasks/{task_id}/resume        → Resume a HITL-paused task
  GET  /tasks/{task_id}/state         → Fetch persisted task state
  GET  /tasks/{task_id}/history       → List checkpoint history (time-travel)
  GET  /api/docs                      → Swagger UI
  GET  /api/redoc                     → ReDoc

Architecture notes:
  - The LangGraph graph is initialised ONCE during lifespan startup (async).
  - The AsyncPostgresSaver checkpointer connects to Neon during startup.
  - All /tasks endpoints are non-blocking; streaming uses SSE.
  - The graph singleton is stored in graph/workflow.py via set_graph().
"""

import sys
import asyncio

# Set SelectorEventLoop on Windows for psycopg compatibility in async mode
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        import uvicorn.loops.asyncio
        uvicorn.loops.asyncio.asyncio_setup = lambda: None
    except ImportError:
        pass

import logging
import os
from contextlib import asynccontextmanager
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

# ── Load .env BEFORE anything reads settings ──────────────────────────────
load_dotenv()

from app.core.config import settings  # noqa: E402
from app.core.database import check_db_health, init_db  # noqa: E402
from app.graph.workflow import build_async_graph, set_graph  # noqa: E402
from app.services.task_service import (  # noqa: E402
    get_task_state,
    list_task_history,
    run_task,
    run_task_stream,
)
from app.services.memory_service import list_memories  # noqa: E402

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG if not settings.is_production else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class TaskRequest(BaseModel):
    """Request body for POST /tasks/run."""

    task: str = Field(
        ...,
        min_length=10,
        max_length=4000,
        description="The task or question for AutoCrew AI to complete.",
        examples=["Write a comprehensive report on the latest AI trends in 2026."],
    )
    stream: bool = Field(
        default=True,
        description=(
            "If true, responses are streamed via Server-Sent Events. "
            "If false, the request blocks until completion."
        ),
    )
    enable_hitl: bool = Field(
        default=False,
        description=(
            "If true, the graph will pause at the HITL node for human review "
            "before the Verifier runs. Resume via POST /tasks/{id}/resume."
        ),
    )


class ResumeRequest(BaseModel):
    """Request body for POST /tasks/{task_id}/resume (HITL)."""

    human_feedback: Optional[str] = Field(
        default=None,
        description=(
            "Optional textual feedback from the human reviewer. "
            "Leave empty to approve the draft as-is and proceed to Verifier."
        ),
    )


class TaskResponse(BaseModel):
    """Response body for blocking (non-streaming) task runs."""

    task_id: str
    final_output: str
    critique_score: float
    iterations: int
    plan: list
    awaiting_human: bool = False
    error: Optional[str] = None


class TaskStateResponse(BaseModel):
    """Response body for GET /tasks/{task_id}/state."""

    task_id: str
    task: str
    plan: list
    draft: str
    critique: str
    critique_score: float
    iteration: int
    awaiting_human: bool
    enable_hitl: bool = False
    final_output: str
    error: Optional[str] = None
    token_usage: list = []
    memory_context: Optional[str] = None


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str
    service: str
    version: str
    environment: str
    groq_configured: bool
    tavily_configured: bool
    model: str
    database: dict
    neon: bool


# ---------------------------------------------------------------------------
# Application lifecycle (lifespan)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager — startup and shutdown hooks.

    Startup sequence:
    1. Log configuration summary.
    2. Initialise the Neon database (enable PGVector, verify connection).
    3. Build the LangGraph graph with AsyncPostgresSaver checkpointer.
    4. Store the graph singleton for use by task_service.

    Shutdown:
    - Log a clean shutdown message (SQLAlchemy disposes the pool automatically).
    """
    # ── Startup ─────────────────────────────────────────────────────────────
    logger.info("=" * 65)
    logger.info("  AutoCrew AI Backend — Starting Up")
    logger.info("=" * 65)
    logger.info("  Environment : %s", settings.environment)
    logger.info("  LLM Model   : %s", settings.groq_model_name)
    logger.info("  Fast Model  : %s", settings.groq_fast_model_name)
    logger.info("  Groq Key    : %s", "✓ set" if settings.groq_api_key else "✗ MISSING")
    logger.info("  Tavily Key  : %s", "✓ set" if settings.tavily_api_key else "✗ not set")
    logger.info("  Database    : %s", settings.database_url[:50] + "...")
    logger.info("  Neon DB     : %s", "✓ yes" if settings.is_neon else "✗ local postgres")
    logger.info("=" * 65)

    if not settings.groq_api_key:
        logger.critical("GROQ_API_KEY is not set! Task requests will fail.")

    # Step 1: Init database (PGVector extension, connection check)
    try:
        await init_db()
    except Exception as exc:
        logger.error("Database initialisation failed: %s", exc)
        logger.warning("Starting without database — checkpointing disabled.")

    # Step 2: Build the LangGraph graph with async checkpointer
    try:
        graph = await build_async_graph(use_checkpointer=True)
        set_graph(graph)
        logger.info("✓ LangGraph graph compiled and ready.")
    except Exception as exc:
        logger.error("Graph compilation failed: %s", exc, exc_info=True)
        # Build without checkpointer as last resort
        try:
            from app.graph.workflow import build_graph
            graph = build_graph(use_checkpointer=False)
            set_graph(graph)
            logger.warning("⚠ Graph running WITHOUT checkpointer (HITL/resume disabled).")
        except Exception as fallback_exc:
            logger.critical("Cannot compile graph: %s", fallback_exc)
            raise

    logger.info("AutoCrew AI backend is ready to handle requests.")

    yield  # ← Application runs here

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("AutoCrew AI backend shutting down.")


# ---------------------------------------------------------------------------
# FastAPI app factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create, configure, and return the FastAPI application."""

    app = FastAPI(
        title="AutoCrew AI",
        description=(
            "Hierarchical multi-agent automation platform powered by LangGraph + Groq + Neon.\n\n"
            "Submit a task and watch a crew of AI agents — Planner, Researcher, Executor, "
            "Critic, and Verifier — collaborate to produce a high-quality deliverable.\n\n"
            "**Key Features:**\n"
            "- 🔄 Real-time streaming via Server-Sent Events\n"
            "- 🔁 Self-critique & revision loop (up to 5 iterations)\n"
            "- 👤 Human-in-the-Loop (HITL) checkpoint support\n"
            "- 🐘 Persistent state via Neon Serverless PostgreSQL\n"
            "- 🔍 Web research via Tavily\n"
        ),
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    # ── CORS ───────────────────────────────────────────────────────────────
    allowed_origins = [
        "http://localhost",
        "http://localhost:3000",    # React / Next.js dev
        "http://localhost:5173",    # Vite dev
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    # In production, restrict to your actual frontend domain
    if settings.is_production:
        import os as _os
        prod_origin = _os.environ.get("FRONTEND_URL", "")
        if prod_origin:
            allowed_origins = [prod_origin]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ─────────────────────────────────────────────────────────────

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["System"],
        summary="Health Check",
    )
    async def health_check():
        """
        Returns the service health status, including database connectivity.

        Performs a lightweight ``SELECT 1`` against the database to verify
        the Neon connection is live.
        """
        db_health = await check_db_health()
        return HealthResponse(
            status="ok" if db_health["status"] == "ok" else "degraded",
            service="AutoCrew AI Backend",
            version="1.0.0",
            environment=settings.environment,
            groq_configured=bool(settings.groq_api_key),
            tavily_configured=bool(settings.tavily_api_key),
            model=settings.groq_model_name,
            database=db_health,
            neon=settings.is_neon,
        )

    @app.post(
        "/tasks/run",
        tags=["Tasks"],
        summary="Run a Task (Streaming SSE or Blocking)",
        response_description="SSE stream of agent events, or blocking JSON response.",
    )
    async def run_task_endpoint(request: TaskRequest):
        """
        Submit a task to AutoCrew AI for multi-agent processing.

        **Streaming mode** (``stream: true``, default):
        Returns a ``text/event-stream`` response. Each SSE event is a JSON object.

        Event types:
        - ``task_start``  — task accepted, ID assigned
        - ``node_update`` — emitted when each agent node completes
        - ``hitl``        — task paused for human review (if ``enable_hitl: true``)
        - ``final``       — the completed deliverable + metadata
        - ``error``       — if an unrecoverable error occurs

        **Blocking mode** (``stream: false``):
        Waits for the full pipeline to complete and returns a JSON body.
        Use streaming for production — blocking mode may time out on long tasks.

        **Example curl (streaming)**:
        ```bash
        curl -X POST http://localhost:8000/tasks/run \\
          -H "Content-Type: application/json" \\
          -d '{"task": "Research and write a report on quantum computing advances in 2026"}'
        ```
        """
        logger.info(
            "[API] POST /tasks/run | stream=%s | task=%.80s…",
            request.stream,
            request.task,
        )

        if request.stream:
            return EventSourceResponse(
                run_task_stream(task=request.task, enable_hitl=request.enable_hitl),
                media_type="text/event-stream",
            )
        else:
            result = await run_task(task=request.task, enable_hitl=request.enable_hitl)
            return TaskResponse(**result)

    @app.post(
        "/tasks/{task_id}/resume",
        tags=["Tasks"],
        summary="Resume a Paused HITL Task",
    )
    async def resume_task_endpoint(task_id: str, request: ResumeRequest):
        """
        Resume a task that is paused awaiting human review.

        Inject optional ``human_feedback`` and the graph will continue
        from the HITL checkpoint. If feedback is provided, the Executor
        will perform one more revision before the Verifier finalises.

        Returns an SSE stream of the remaining agent steps.
        """
        logger.info(
            "[API] POST /tasks/%s/resume | feedback=%s",
            task_id,
            bool(request.human_feedback),
        )

        state = await get_task_state(task_id)
        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"Task '{task_id}' not found.",
            )
        if not state.get("awaiting_human"):
            raise HTTPException(
                status_code=400,
                detail=f"Task '{task_id}' is not paused for human review.",
            )

        return EventSourceResponse(
            run_task_stream(
                task=state["task"],
                task_id=task_id,
                human_feedback=request.human_feedback,
            ),
            media_type="text/event-stream",
        )

    @app.get(
        "/tasks/{task_id}/state",
        tags=["Tasks"],
        summary="Get Task State",
        response_model=TaskStateResponse,
    )
    async def get_task_state_endpoint(task_id: str):
        """
        Retrieve the persisted state of a task by its ID.

        Useful for:
        - Polling task status from the frontend
        - Checking whether a task is ``awaiting_human``
        - Displaying the current draft to a human reviewer
        - Debugging completed tasks
        """
        state = await get_task_state(task_id)
        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"Task '{task_id}' not found.",
            )
        return TaskStateResponse(**state)

    @app.get(
        "/tasks/{task_id}/history",
        tags=["Tasks"],
        summary="List Task Checkpoint History (Time-Travel)",
    )
    async def get_task_history_endpoint(
        task_id: str,
        limit: int = Query(default=10, ge=1, le=50, description="Max checkpoints to return"),
    ):
        """
        List the checkpoint history for a task in reverse chronological order.
        """
        checkpoints = await list_task_history(task_id, limit=limit)
        return {
            "task_id": task_id,
            "checkpoint_count": len(checkpoints),
            "checkpoints": checkpoints,
        }

    @app.get(
        "/memory",
        tags=["Memory"],
        summary="List Long-Term Memories",
    )
    async def list_memories_endpoint(
        limit: int = Query(default=20, ge=1, le=100, description="Max memories to return"),
    ):
        """
        List stored long-term task memories (RAG vector store).
        Returns summaries of past completed tasks for observability.
        """
        memories = await list_memories(limit=limit)
        return {"count": len(memories), "memories": memories}

    return app


# ---------------------------------------------------------------------------
# Application singleton
# ---------------------------------------------------------------------------

app = create_app()


# ---------------------------------------------------------------------------
# Direct execution entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=not settings.is_production,
        log_level="debug" if not settings.is_production else "info",
    )
