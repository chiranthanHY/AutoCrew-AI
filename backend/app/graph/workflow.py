"""
graph/workflow.py — LangGraph StateGraph for AutoCrew AI
---------------------------------------------------------
Neon Serverless PostgreSQL + langgraph-checkpoint-postgres edition.

This file wires together all five specialist agents into a directed,
conditional StateGraph with:

  - PostgresSaver (sync) for non-async contexts
  - AsyncPostgresSaver for fully async streaming
  - HITL interrupt support
  - Conditional routing with critique loop
  - Graceful error handling

Graph topology:
  ┌───────────┐     ┌────────────┐     ┌──────────┐
  │  Planner  │────▶│ Researcher │────▶│ Executor │◀─────────┐
  └───────────┘     └────────────┘     └──────────┘          │
                                             │                │
                                        ┌────▼────┐  score<8  │
                                        │  Critic │──────────┘
                                        └────┬────┘
                                    score≥8  │ or max_iter
                                        ┌────▼────────┐
                                        │  [HITL]     │  optional pause
                                        └────┬────────┘
                                        ┌────▼────┐
                                        │Verifier │
                                        └────┬────┘
                                        ┌────▼────┐
                                        │   END   │
                                        └─────────┘

Checkpointer Notes (Neon)
--------------------------
- ``langgraph-checkpoint-postgres`` v2+ uses psycopg3 under the hood.
- ``PostgresSaver`` (sync) wraps ``psycopg.Connection``.
- ``AsyncPostgresSaver`` wraps ``psycopg.AsyncConnection``.
- Call ``.setup()`` once at startup to create checkpoint tables.
- Pass ``sslmode=require`` in the connection string for Neon.
"""

import logging
from typing import Any, Dict, Literal

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph

from app.agents.critic import CriticAgent
from app.agents.executor import ExecutorAgent
from app.agents.planner import PlannerAgent
from app.agents.researcher import ResearcherAgent
from app.agents.verifier import VerifierAgent
from app.core.config import settings
from app.schemas.state import AgentState

logger = logging.getLogger(__name__)


# ===========================================================================
# LLM Factory
# ===========================================================================


def _make_llm(model_name: str | None = None, temperature: float | None = None) -> ChatGroq:
    """
    Create a configured ChatGroq instance.

    Args:
        model_name: Override ``settings.groq_model_name`` if provided.
        temperature: Override ``settings.groq_temperature`` if provided.

    Returns:
        ChatGroq: Ready-to-use LangChain LLM.
    """
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=model_name or settings.groq_model_name,
        temperature=temperature if temperature is not None else settings.groq_temperature,
        max_retries=6,
    )


# ===========================================================================
# Node functions
# ===========================================================================


def planner_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Planner
    Converts the raw user task into a structured, multi-step execution plan.
    Also retrieves long-term memory context from vector store for the Executor.
    """
    logger.info("[Workflow] ▶ planner_node | task_id=%s", state.get("task_id"))
    agent = PlannerAgent(llm=_make_llm())
    try:
        result = agent.invoke(state)
        # Retrieve relevant memories async-safely via asyncio
        import asyncio
        try:
            from app.services.memory_service import retrieve_relevant_memories
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We are inside an async context — schedule as a task and skip if unavailable
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, retrieve_relevant_memories(state.get("task", "")))
                    memory_context = future.result(timeout=10)
            else:
                memory_context = asyncio.run(retrieve_relevant_memories(state.get("task", "")))
            if memory_context:
                result["memory_context"] = memory_context
                logger.info("[Workflow] Memory context injected (%d chars).", len(memory_context))
        except Exception as mem_exc:
            logger.debug("[Workflow] Memory retrieval skipped: %s", mem_exc)
        return result
    except Exception as exc:
        logger.error("[Workflow] planner_node FAILED: %s", exc, exc_info=True)
        return {"error": f"Planner failed: {exc}", "plan": [], "token_usage": []}


def researcher_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Researcher
    Runs targeted Tavily web searches and synthesises structured findings.
    Gracefully skipped when TAVILY_API_KEY is not configured.
    """
    logger.info("[Workflow] ▶ researcher_node | task_id=%s", state.get("task_id"))
    if not settings.tavily_api_key:
        logger.warning("[Workflow] TAVILY_API_KEY not set — skipping web research.")
        return {
            "research_results": [
                {
                    "heading": "Note",
                    "summary": "Web research was skipped (no TAVILY_API_KEY configured).",
                    "sources": [],
                }
            ]
        }
    try:
        agent = ResearcherAgent(
            llm=_make_llm(model_name=settings.groq_fast_model_name),
            max_queries=3,
        )
        result = agent.invoke(state)
        # Attach researcher token usage
        result["token_usage"] = [agent.last_token_usage] if agent.last_token_usage else []
        return result
    except Exception as exc:
        logger.error("[Workflow] researcher_node FAILED: %s", exc, exc_info=True)
        return {
            "research_results": [
                {"heading": "Research Error", "summary": str(exc), "sources": []}
            ],
            "token_usage": [],
        }


def executor_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Executor
    Produces (or revises) the written deliverable based on plan + research.
    """
    logger.info(
        "[Workflow] ▶ executor_node | iteration=%d | task_id=%s",
        state.get("iteration", 0),
        state.get("task_id"),
    )
    agent = ExecutorAgent(llm=_make_llm())
    try:
        return agent.invoke(state)
    except Exception as exc:
        logger.error("[Workflow] executor_node FAILED: %s", exc, exc_info=True)
        return {"error": f"Executor failed: {exc}"}


def critic_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Critic
    Reviews the current draft and returns a numeric score + feedback.
    Sets ``state["next"]`` to control downstream routing.
    """
    logger.info(
        "[Workflow] ▶ critic_node | iteration=%d | task_id=%s",
        state.get("iteration", 0),
        state.get("task_id"),
    )
    agent = CriticAgent(llm=_make_llm())
    try:
        return agent.invoke(state)
    except Exception as exc:
        logger.error("[Workflow] critic_node FAILED: %s", exc, exc_info=True)
        # If critic explodes, skip loop and go to verifier with what we have
        return {
            "critique": f"Critique unavailable due to error: {exc}",
            "critique_score": 8.0,   # treat as passing score
            "next": "verifier",
            "error": f"Critic failed: {exc}",
        }


def hitl_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Human-in-the-Loop (HITL)
    Pauses the graph for optional human review.  If human feedback is
    present in state it is consumed here and factored into the next
    Executor revision.  The actual pause mechanism is handled by
    LangGraph's interrupt() — this node just marks the state transition.
    """
    logger.info("[Workflow] ▶ hitl_node | task_id=%s", state.get("task_id"))
    feedback = state.get("human_feedback")
    if feedback:
        logger.info("[Workflow] Human feedback received: %s", feedback[:120])
        return {
            "awaiting_human": False,
            "messages": [
                HumanMessage(content=f"[Human Reviewer Feedback]: {feedback}")
            ],
        }
    # No feedback yet — signal waiting state
    return {"awaiting_human": True}


def verifier_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Verifier
    Performs a final editorial pass on the approved draft and writes
    ``final_output`` — the definitive response returned to the user.
    Also stores the completed task in long-term memory.
    """
    logger.info("[Workflow] ▶ verifier_node | task_id=%s", state.get("task_id"))
    agent = VerifierAgent(llm=_make_llm())
    try:
        result = agent.invoke(state)
        # Store memory of this completed task
        import asyncio
        try:
            from app.services.memory_service import store_task_memory
            task_id = state.get("task_id", "")
            task = state.get("task", "")
            final_output = result.get("final_output", state.get("draft", ""))
            critique_score = state.get("critique_score", 0.0)
            iteration = state.get("iteration", 0)
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(
                        asyncio.run,
                        store_task_memory(task_id, task, final_output, critique_score, iteration)
                    ).result(timeout=10)
            else:
                asyncio.run(store_task_memory(task_id, task, final_output, critique_score, iteration))
            logger.info("[Workflow] ✓ Task memory stored for task_id=%s", task_id)
        except Exception as mem_exc:
            logger.debug("[Workflow] Memory storage skipped: %s", mem_exc)
        return result
    except Exception as exc:
        logger.error("[Workflow] verifier_node FAILED: %s", exc, exc_info=True)
        return {
            "final_output": state.get("draft", "An error occurred during verification."),
            "error": f"Verifier failed: {exc}",
            "next": "END",
            "token_usage": [],
        }


def error_node(state: AgentState) -> Dict[str, Any]:
    """
    Node: Error Handler
    Terminal node reached when an unrecoverable error has been detected.
    Always sets ``final_output`` so the API can return a meaningful message.
    """
    error_msg = state.get("error", "An unknown error occurred.")
    logger.error(
        "[Workflow] ▶ error_node | error=%s | task_id=%s",
        error_msg,
        state.get("task_id"),
    )
    return {
        "final_output": (
            f"⚠️ AutoCrew AI encountered an error and could not complete this task.\n\n"
            f"**Error:** {error_msg}\n\n"
            f"Please check the logs for more details."
        ),
        "next": "END",
    }


# ===========================================================================
# Conditional routing functions
# ===========================================================================


def route_after_critic(
    state: AgentState,
) -> Literal["executor", "hitl", "verifier", "error"]:
    """
    Router called after the Critic node.

    Decision matrix
    ---------------
    1. If ``state["error"]`` is set → ``error`` node immediately.
    2. If max iterations exceeded   → force ``verifier`` (safety valve).
    3. If score >= threshold AND human review enabled → ``hitl``.
    4. If score >= threshold         → ``verifier``.
    5. Otherwise                     → ``executor`` (revision loop).
    """
    if state.get("error"):
        logger.warning("[Router] Error detected → routing to error node.")
        return "error"

    iteration = state.get("iteration", 0)
    score = state.get("critique_score", 0.0)
    next_node = state.get("next", "executor")

    logger.info(
        "[Router] after_critic | score=%.1f | iteration=%d | next=%s",
        score,
        iteration,
        next_node,
    )

    # Safety valve: force verifier after too many iterations
    if iteration >= settings.max_iterations:
        logger.warning(
            "[Router] Max iterations (%d) reached — forcing verifier/hitl.",
            settings.max_iterations,
        )
        if state.get("enable_hitl", False):
            return "hitl"
        return "verifier"

    # Normal routing from Critic's own decision
    if next_node == "verifier":
        if state.get("enable_hitl", False):
            logger.info("[Router] HITL is enabled — routing to hitl node.")
            return "hitl"
        return "verifier"

    return "executor"


def route_after_hitl(
    state: AgentState,
) -> Literal["executor", "verifier"]:
    """
    Router called after the HITL node.

    - If human provided feedback → route back to ``executor`` for revision.
    - If human approved without changes → route to ``verifier``.
    """
    feedback = state.get("human_feedback")
    if feedback and feedback.strip():
        logger.info("[Router] Human feedback present → routing to executor for revision.")
        return "executor"
    logger.info("[Router] No human feedback — routing to verifier.")
    return "verifier"


# ===========================================================================
# Checkpointer factory
# ===========================================================================


# Caching checkpointer pools globally to prevent connection leaks across API reloads
_sync_pool = None
_async_pool = None


def _create_sync_checkpointer():
    global _sync_pool
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg_pool import ConnectionPool
        from psycopg.rows import dict_row

        conn_string = settings.postgres_url
        logger.info(
            "[Workflow] Creating PostgresSaver pool | neon=%s | url=%.40s...",
            settings.is_neon,
            conn_string,
        )
        if _sync_pool is None:
            _sync_pool = ConnectionPool(
                conninfo=conn_string,
                max_size=5,
                kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": None}
            )
        checkpointer = PostgresSaver(_sync_pool)
        checkpointer.setup()
        logger.info("[Workflow] ✓ PostgresSaver checkpointer ready.")
        return checkpointer
    except Exception as exc:
        logger.warning(
            "[Workflow] PostgresSaver pool creation failed (%s) — falling back to no checkpointer.",
            exc,
        )
        return None


async def _create_async_checkpointer():
    global _async_pool
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool
        from psycopg.rows import dict_row

        conn_string = settings.postgres_url
        logger.info(
            "[Workflow] Creating AsyncPostgresSaver pool | neon=%s | url=%.40s...",
            settings.is_neon,
            conn_string,
        )
        if _async_pool is None:
            _async_pool = AsyncConnectionPool(
                conninfo=conn_string,
                max_size=5,
                open=False,
                kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": None}
            )
            await _async_pool.open()
            
        checkpointer = AsyncPostgresSaver(_async_pool)
        await checkpointer.setup()
        logger.info("[Workflow] ✓ AsyncPostgresSaver checkpointer ready.")
        return checkpointer
    except Exception as exc:
        logger.warning(
            "[Workflow] AsyncPostgresSaver pool creation failed (%s) — falling back to sync.",
            exc,
        )
        return None


# ===========================================================================
# Graph builder
# ===========================================================================


def _build_graph_topology(builder: StateGraph) -> StateGraph:
    """
    Register all nodes and edges on the StateGraph builder.
    Shared between sync and async graph compilation.
    """
    # -------------------------------------------------------------------
    # Register nodes
    # -------------------------------------------------------------------
    builder.add_node("planner", planner_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("executor", executor_node)
    builder.add_node("critic", critic_node)
    builder.add_node("hitl", hitl_node)
    builder.add_node("verifier", verifier_node)
    builder.add_node("error", error_node)

    # -------------------------------------------------------------------
    # Entry point & fixed edges
    # -------------------------------------------------------------------
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "researcher")
    builder.add_edge("researcher", "executor")
    builder.add_edge("executor", "critic")

    # -------------------------------------------------------------------
    # Conditional edges (routing logic)
    # -------------------------------------------------------------------
    builder.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "executor": "executor",
            "hitl": "hitl",
            "verifier": "verifier",
            "error": "error",
        },
    )

    builder.add_conditional_edges(
        "hitl",
        route_after_hitl,
        {
            "executor": "executor",
            "verifier": "verifier",
        },
    )

    # -------------------------------------------------------------------
    # Terminal edges
    # -------------------------------------------------------------------
    builder.add_edge("verifier", END)
    builder.add_edge("error", END)

    return builder


def build_graph(use_checkpointer: bool = True):
    """
    Construct and compile the AutoCrew AI StateGraph (sync variant).

    The async variant is preferred for FastAPI — use ``build_async_graph()``.

    Args:
        use_checkpointer: When True (default), attaches a PostgresSaver so
            the graph state is persisted between API calls, enabling
            streaming, HITL, and resumability.

    Returns:
        CompiledGraph: Ready-to-invoke LangGraph graph.
    """
    builder = StateGraph(AgentState)
    _build_graph_topology(builder)

    if use_checkpointer:
        checkpointer = _create_sync_checkpointer()
        if checkpointer:
            return builder.compile(checkpointer=checkpointer, interrupt_before=["hitl"])

    logger.info("[Workflow] Compiling graph WITHOUT checkpointer.")
    return builder.compile()


async def build_async_graph(use_checkpointer: bool = True):
    """
    Construct and compile the AutoCrew AI StateGraph (async variant).

    Preferred for production FastAPI deployments — uses AsyncPostgresSaver
    which avoids blocking the event loop during checkpoint reads/writes.

    Args:
        use_checkpointer: When True, attaches an AsyncPostgresSaver.

    Returns:
        CompiledGraph: Ready-to-invoke async LangGraph graph.
    """
    builder = StateGraph(AgentState)
    _build_graph_topology(builder)

    if use_checkpointer:
        # Try async first (preferred), fall back to sync, then no checkpointer
        checkpointer = await _create_async_checkpointer()
        if checkpointer is None:
            checkpointer = _create_sync_checkpointer()
        if checkpointer:
            logger.info("[Workflow] Compiling async graph WITH checkpointer.")
            return builder.compile(checkpointer=checkpointer, interrupt_before=["hitl"])

    logger.info("[Workflow] Compiling async graph WITHOUT checkpointer.")
    return builder.compile()


# ===========================================================================
# Module-level graph singleton
# ===========================================================================

# The module-level graph singleton is intentionally lazy-loaded.
# It is initialised during the FastAPI lifespan startup in main.py.
# Use get_graph() after startup is complete.

_graph = None


def get_graph():
    """
    Return the compiled, module-level singleton graph.

    Raises RuntimeError if the graph has not been initialised yet
    (i.e., if called before the FastAPI lifespan has completed startup).
    """
    if _graph is None:
        raise RuntimeError(
            "Graph not initialised. Call init_graph() during application startup "
            "(see lifespan in main.py)."
        )
    return _graph


def set_graph(graph) -> None:
    """Set the module-level graph singleton. Called during startup."""
    global _graph
    _graph = graph
    logger.info("[Workflow] Graph singleton set: %s", type(graph).__name__)
